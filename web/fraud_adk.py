"""Native ADK function execution. Fake-model fixtures never construct a Gemini client."""
import json
import os

from google.adk.agents import LlmAgent
from google.adk.agents.run_config import RunConfig
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from pydantic import PrivateAttr

from fraud_agent import MAX_OUTPUT_TOKENS, MODEL, SYSTEM, TOOLS
from fraud_desk import cues
from lab import LabError, encoded


def fixture_choice(packet):
    """Test fixture policy, not intelligence. Decisions use the real preceding tool results."""
    observations = packet['observations']
    by_tool = {o['tool']: o['result'] for o in observations}
    combined = ' '.join([packet['story'], packet['message_transcript']] + [a['text'] for a in packet['customer_replies']])
    suspicious = len(cues(combined)) >= 2
    if packet['ingestion_flags'] and 'search_reviewed_cases' not in by_tool:
        return 'search_reviewed_cases', {'query': 'safe_account impersonation pressure secrecy', 'purpose': 'Check the reviewed case behind the recipient flag.'}
    if 'get_transactions' not in by_tool:
        return 'get_transactions', {'event_ids': packet['event_ids'], 'purpose': 'Verify the specific transfer reported by this customer.'}
    if suspicious and 'search_reviewed_cases' not in by_tool:
        return 'search_reviewed_cases', {'query': 'safe_account impersonation pressure secrecy', 'purpose': 'Look for reviewed examples of the reported pattern.'}
    memories = by_tool.get('search_reviewed_cases', {}).get('matches', [])
    if memories and not packet['customer_replies']:
        return 'ask_customer', {'question': memories[0]['next_question'], 'purpose': 'Clarify whether the reviewed pattern applies to this customer.'}
    legitimate = any(word in combined.lower() for word in ('groceries', 'received my items', 'recognized the merchant'))
    if not suspicious and not legitimate and not packet['customer_replies']:
        return 'ask_customer', {'question': 'Who asked you to make this transfer, and what did they promise in return?', 'purpose': 'The report does not yet explain why the customer sent money.'}
    if suspicious and not memories and 'compare_behavior' not in by_tool:
        return 'compare_behavior', {'window_days': 14, 'purpose': 'Compare the transfer with recent observed spending.'}
    if suspicious and 'trace_recipient' not in by_tool:
        return 'trace_recipient', {'recipient_id': by_tool['get_transactions']['transactions'][0]['to_account'], 'purpose': 'Check related transfers without treating a shared recipient as proof.'}
    return 'submit_for_review', {
        'assessment': 'suspected_scam' if suspicious else 'likely_legitimate' if legitimate else 'needs_information',
        'summary': 'The report and recorded transfer support investigating possible impersonation. An analyst must verify the allegation.' if suspicious else 'The customer describes an ordinary purchase. The available evidence does not independently establish a scam.',
        'evidence_ids': packet['event_ids'], 'memory_ids': [m['id'] for m in memories],
        'uncertainties': ['Caller identity and the customer account of events need analyst verification.'],
        'questions': [] if packet['customer_replies'] else ["Have you verified the caller through your bank's official support channel?"] if suspicious else [],
        'action': 'request_recall' if suspicious else 'support_followup',
        'customer_message': 'Your report is ready for analyst review. No refund or liability decision has been made.',
        'purpose': 'Submit the evidence and remaining uncertainty for human review.'}


class FakeInvestigator(BaseLlm):
    """Inject a chooser to exercise arbitrary tool paths through the actual ADK runtime."""
    model: str = 'minttown-fake-investigator'
    input_tokens: int = 1000
    output_tokens: int = 120
    thinking_tokens: int = 0
    _chooser: list = PrivateAttr(default_factory=list)
    _requests: list = PrivateAttr(default_factory=list)

    def __init__(self, chooser=None, **kwargs):
        super().__init__(**kwargs)
        self._chooser.append(chooser or fixture_choice)

    async def generate_content_async(self, llm_request, stream=False):
        packet = json.loads(llm_request.contents[-1].parts[0].text)
        self._requests.append(packet)
        name, args = self._chooser[0](packet)
        yield LlmResponse(finish_reason='STOP', content=types.Content(role='model', parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))]),
                          usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=self.input_tokens,
                              candidates_token_count=self.output_tokens, thoughts_token_count=self.thinking_tokens))


def tools_for(controller, run_id):
    def invoke(name, args, purpose, context):
        result = controller.tool(run_id, name, args, purpose)
        # One generation per HTTP step. Next invocation reads the durable observations.
        context.actions.escalate = True
        context.actions.skip_summarization = True
        return result

    def get_transactions(event_ids: list[str], purpose: str, tool_context: ToolContext) -> dict:
        """Verify IDs from the current report; an empty list selects all reported transfers."""
        return invoke('get_transactions', {'event_ids': event_ids}, purpose, tool_context)

    def compare_behavior(window_days: int, purpose: str, tool_context: ToolContext) -> dict:
        """Compare this customer's prior spending over 1–30 days. These are descriptive checks, not an ML verdict."""
        return invoke('compare_behavior', {'window_days': window_days}, purpose, tool_context)

    def trace_recipient(recipient_id: str, purpose: str, tool_context: ToolContext) -> dict:
        """Find up to ten transfers to a recipient appearing in this report, without exposing other customer profiles."""
        return invoke('trace_recipient', {'recipient_id': recipient_id}, purpose, tool_context)

    def search_reviewed_cases(query: str, purpose: str, tool_context: ToolContext) -> dict:
        """Retrieve up to three analyst-approved case memories using relevant words or the recipient account."""
        return invoke('search_reviewed_cases', {'query': query}, purpose, tool_context)

    def ask_customer(question: str, purpose: str, tool_context: ToolContext) -> dict:
        """Save one missing-information question and pause. The local customer reply form resumes the case."""
        return invoke('ask_customer', {'question': question}, purpose, tool_context)

    def submit_for_review(assessment: str, summary: str, evidence_ids: list[str], memory_ids: list[str],
                          uncertainties: list[str], questions: list[str], action: str, customer_message: str,
                          purpose: str, tool_context: ToolContext) -> dict:
        """Submit for human review. Assessment: suspected_scam, needs_information or likely_legitimate.
        Cite every verified reported transaction and only retrieved memories. Action: request_recall
        (proposal only, for suspected_scam) or support_followup. This never approves a case or moves money.
        """
        return invoke('submit_for_review', dict(assessment=assessment, summary=summary, evidence_ids=evidence_ids,
                      memory_ids=memory_ids, uncertainties=uncertainties, questions=questions, action=action,
                      customer_message=customer_message), purpose, tool_context)

    return [get_transactions, compare_behavior, trace_recipient, search_reviewed_cases, ask_customer, submit_for_review]


async def run_turn(controller, run, packet):
    mode = run['context']['provider']; client = None
    if mode == 'gemini':
        if not controller.live_enabled(): raise LabError('Live Gemini is off.', 409)
        from google import genai
        from google.adk.models.google_llm import Gemini
        client = genai.Client(vertexai=True, project=os.environ['GOOGLE_CLOUD_PROJECT'],
                              location=os.getenv('GOOGLE_CLOUD_LOCATION', 'global'),
                              http_options=types.HttpOptions(timeout=25000, retry_options=types.HttpRetryOptions(attempts=1)))
        inner = Gemini(model=MODEL, client=client, use_interactions_api=False, retry_options=types.HttpRetryOptions(attempts=1))
    else:
        inner = controller.model_factory() if controller.model_factory else FakeInvestigator()

    class MeteredModel(BaseLlm):
        model: str = MODEL

        async def generate_content_async(self, llm_request, stream=False):
            turn_id = controller.reserve(run['id'], llm_request)
            seen = False
            async for response in inner.generate_content_async(llm_request, stream=False):
                if seen: raise LabError('Unexpected multiple model responses.', 502)
                controller.record_response(turn_id, response); seen = True
                yield response
            if not seen: raise LabError('The model returned no response; reservation retained.', 502)

    sessions = InMemorySessionService()
    await sessions.create_session(app_name='minttown_fraud', user_id=packet['customer_id'], session_id=run['id'])
    agent = LlmAgent(name='fraud_investigator', model=MeteredModel(), instruction=SYSTEM,
                     tools=tools_for(controller, run['id']),
                     generate_content_config=types.GenerateContentConfig(max_output_tokens=MAX_OUTPUT_TOKENS,
                         temperature=.1, thinking_config=types.ThinkingConfig(thinking_level='MINIMAL', include_thoughts=False),
                         tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='ANY', allowed_function_names=list(TOOLS)))))
    runner = Runner(agent=agent, app_name='minttown_fraud', session_service=sessions)
    trace = []
    try:
        async for event in runner.run_async(user_id=packet['customer_id'], session_id=run['id'],
                new_message=types.Content(role='user', parts=[types.Part(text=encoded(packet))]), run_config=RunConfig(max_llm_calls=1)):
            trace.append({'author': event.author, 'function_calls': [c.name for c in event.get_function_calls()],
                          'function_responses': [r.name for r in event.get_function_responses()], 'stop_after_tool': bool(event.actions.escalate)})
    finally:
        await runner.close()
        if client is not None: await client.aio.aclose()
    return trace

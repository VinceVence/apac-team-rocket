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
from fraud_desk import cues, LESSON, QUESTION
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
    if packet.get('guided_demo'):
        if packet.get('warehouse_available') and 'get_customer_features' not in by_tool:
            return 'get_customer_features',{'purpose':'Read this customer’s pinned transaction history.'}
        if 'run_fraud_detectors' not in by_tool:
            return 'run_fraud_detectors',{'detector_ids':['device_integrity_v1','message_intent_v1'],'purpose':'Compare device evidence with the payment request’s warning signals.'}
        if 'get_complaint_guidance' not in by_tool:
            return 'get_complaint_guidance',{'purpose':'Check the institution-led complaint handling steps.'}
        suspicious=True
    if suspicious and not packet.get('guided_demo') and 'search_reviewed_cases' not in by_tool:
        return 'search_reviewed_cases', {'query': 'safe_account impersonation pressure secrecy', 'purpose': 'Look for reviewed examples of the reported pattern.'}
    memories = by_tool.get('search_reviewed_cases', {}).get('matches', [])
    if memories and not packet['customer_replies']:
        return 'ask_customer', {'question': memories[0]['next_question'], 'purpose': 'Clarify whether the reviewed pattern applies to this customer.'}
    legitimate = any(word in combined.lower() for word in ('groceries', 'received my items', 'recognized the merchant'))
    if not suspicious and not legitimate and not packet['customer_replies']:
        return 'ask_customer', {'question': 'Who asked you to make this transfer, and what did they promise in return?', 'purpose': 'The report does not yet explain why the customer sent money.'}
    if suspicious and not packet.get('guided_demo') and not memories and 'compare_behavior' not in by_tool:
        return 'compare_behavior', {'window_days': 14, 'purpose': 'Compare the transfer with recent observed spending.'}
    if suspicious and not packet.get('guided_demo') and 'trace_recipient' not in by_tool:
        return 'trace_recipient', {'recipient_id': by_tool['get_transactions']['transactions'][0]['to_account'], 'purpose': 'Check related transfers without treating a shared recipient as proof.'}
    return 'submit_for_review', {
        'assessment': 'suspected_scam' if suspicious else 'likely_legitimate' if legitimate else 'needs_information',
        'summary': 'The report and recorded transfer support investigating possible impersonation. An analyst must verify the allegation.' if suspicious else 'The customer describes an ordinary purchase. The available evidence does not independently establish a scam.',
        'evidence_ids': packet['event_ids'], 'memory_ids': [m['id'] for m in memories],
        'uncertainties': ['Caller identity and the customer account of events need analyst verification.'],
        'questions': [] if packet['customer_replies'] else ["Have you verified the caller through your bank's official support channel?"] if suspicious else [],
        'action': 'request_recall' if suspicious else 'support_followup',
        'customer_message': 'Your report is ready for analyst review. No refund or liability decision has been made.',
        'lesson':LESSON,'followup_question':QUESTION,
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

    def get_customer_features(purpose: str, tool_context: ToolContext) -> dict:
        """Read this case customer's spending, frequency, merchants and device indicators from its pinned BigQuery snapshot. Required before submission when warehouse_available is true."""
        return invoke('get_customer_features',{},purpose,tool_context)

    def train_behavior_model(purpose: str, tool_context: ToolContext) -> dict:
        """Optional: after get_customer_features, train or reuse a bounded local CPU anomaly model on up to 100 BigQuery customer histories. Use only if it adds evidence beyond descriptive analysis. Unsupervised, no fraud probability, no automatic bank action."""
        return invoke('train_behavior_model',{},purpose,tool_context)

    def get_complaint_guidance(purpose: str, tool_context: ToolContext) -> dict:
        """Read the curated Philippine complaint checklist and BSP source links. Supports institution-led verification and escalation; no guaranteed recovery, invented deadlines or liability decision."""
        return invoke('get_complaint_guidance',{},purpose,tool_context)

    def run_fraud_detectors(detector_ids:list[str],purpose:str,tool_context:ToolContext)->dict:
        """Choose one to three registered detectors: device_integrity_v1, payment_velocity_v1, message_intent_v1. Uses only verified, frozen case transactions; rule signals are not fraud probabilities."""
        return invoke('run_fraud_detectors',{'detector_ids':detector_ids},purpose,tool_context)

    def submit_for_review(assessment: str, summary: str, evidence_ids: list[str], memory_ids: list[str],
                          uncertainties: list[str], questions: list[str], action: str, customer_message: str,
                          lesson: str, followup_question: str, purpose: str, tool_context: ToolContext) -> dict:
        """Submit for human review. Assessment: suspected_scam, needs_information or likely_legitimate.
        Cite every verified reported transaction and only retrieved memories. Action: request_recall
        (proposal only, for suspected_scam) or support_followup. Include a case-specific lesson and future question for the analyst. This never approves a case or moves money.
        """
        return invoke('submit_for_review', dict(assessment=assessment, summary=summary, evidence_ids=evidence_ids,
                      memory_ids=memory_ids, uncertainties=uncertainties, questions=questions, action=action,
                      customer_message=customer_message,lesson=lesson,followup_question=followup_question), purpose, tool_context)

    return [get_transactions, compare_behavior, trace_recipient, search_reviewed_cases, ask_customer, submit_for_review,
            get_customer_features,train_behavior_model,get_complaint_guidance,run_fraud_detectors]


def available_tools(packet):
    """Expose useful capabilities for this evidence state, without fixing their order."""
    observed={o['tool']:o['result'] for o in packet['observations']}
    verified={t['id'] for o in packet['observations'] if o['tool']=='get_transactions' for t in o['result']['transactions']}
    complete=set(packet['event_ids'])<=verified
    excluded={name for name in ('get_customer_features','get_complaint_guidance','train_behavior_model') if name in observed}
    if complete:excluded.add('get_transactions')
    else:excluded.update(('submit_for_review','run_fraud_detectors'))
    if not packet['warehouse_available']:excluded.update(('get_customer_features','train_behavior_model'))
    elif 'get_customer_features' not in observed:excluded.update(('submit_for_review','train_behavior_model'))
    if packet.get('guided_demo') and 'run_fraud_detectors' not in observed:excluded.add('submit_for_review')
    if packet.get('guided_demo') and packet.get('reviewed_memory_count')==0:excluded.add('search_reviewed_cases')
    return tuple(name for name in TOOLS if name not in excluded)


async def run_turn(controller, run, packet, *, instruction=SYSTEM, tools_factory=tools_for, allowed_tools=TOOLS, agent_name='fraud_investigator'):
    if agent_name=='fraud_investigator':allowed_tools=available_tools(packet)
    exposed=[tool for tool in tools_factory(controller,run['id']) if tool.__name__ in allowed_tools]
    packet={**packet,'available_next_tools':list(allowed_tools)}
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
    agent = LlmAgent(name=agent_name, model=MeteredModel(), instruction=instruction,
                     tools=exposed,
                     generate_content_config=types.GenerateContentConfig(max_output_tokens=MAX_OUTPUT_TOKENS,
                         thinking_config=types.ThinkingConfig(thinking_level='MINIMAL', include_thoughts=False),
                         tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode='ANY', allowed_function_names=list(allowed_tools)))))
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

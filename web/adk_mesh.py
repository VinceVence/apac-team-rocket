"""Google ADK graph dispatch for the five-role mesh, one bounded turn per request.

ADK executes the route graph; Gemini's role decision is handled by the existing
metered adapter. SQLite owns durable messages and optimistic turn concurrency.
"""
import asyncio
import importlib.metadata
import json

from lab import LabError, encoded
from mesh import ROLES


def runtime():
    try:
        version = importlib.metadata.version('google-adk')
    except importlib.metadata.PackageNotFoundError:
        return {'engine': 'local', 'label': 'Local router · start with uv run --locked python for Google ADK', 'google_adk': None}
    return {'engine': 'google-adk', 'label': 'Google ADK ' + version + ' · typed graph routing', 'google_adk': version}


def dispatch(mesh, identifier, expected_step):
    info = runtime()
    if info['engine'] == 'local': return {**mesh.step(identifier, expected_step), 'runtime': info}
    from google.adk import Event, Workflow
    from google.adk.runners import InMemoryRunner

    failure = []

    def route_turn(node_input: str):
        request = json.loads(node_input)
        with mesh.lab.lock:
            role = mesh.run(request['run_id'])['active_role']
        if role not in ROLES: raise LabError('Unknown agent role.', 422)
        return Event(route=role, output=request)

    def role_node(role):
        def execute(node_input: dict):
            try:
                with mesh.lab.lock:
                    current = mesh.run(node_input['run_id'])
                    if current['active_role'] != role: raise LabError('The active role changed before dispatch.', 409)
                result = mesh.step(node_input['run_id'], node_input['expected_step'])
                return Event(output={'run_id': result['id'], 'status': result['status'], 'step': result['step']})
            except LabError as exc:
                failure.append(exc)
                return Event(output={'status': 'failed', 'error': str(exc)})
        execute.__name__ = role
        return execute

    active_roles=mesh.run(identifier)['playbook']['role_ids']
    graph = Workflow(name='minttown_playbook_mesh', max_concurrency=1,
                     edges=[('START', route_turn), (route_turn, {role: role_node(role) for role in active_roles})])

    async def run_graph():
        runner = InMemoryRunner(agent=graph, app_name='minttown_mesh')
        return await runner.run_debug(encoded({'run_id': identifier, 'expected_step': expected_step}),
                                      user_id='local_operator', session_id=identifier + '-' + str(expected_step), quiet=True)

    events = asyncio.run(run_graph())
    trace = [{'author': e.author, 'node': e.node_info.path if e.node_info else '',
              'route': e.actions.route if e.actions else None} for e in events]
    with mesh.lab.lock, mesh.lab.db:
        mesh.lab.db.execute("UPDATE mesh_turns SET router_trace=? WHERE run_id=? AND seq=? AND router_trace='[]'", (encoded(trace), identifier, expected_step))
    if failure: raise failure[0]
    return {**mesh.run(identifier), 'runtime': info}

# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import shlex
import typing as t
import xml.etree.ElementTree as ET
from pathlib import Path

from .api import ArtifactManager

LOGGER = logging.getLogger(__name__)


def _is_job_retry() -> bool:
    try:
        return int(os.getenv('CI_JOB_RETRY', '0')) > 0
    except ValueError:
        return False


def _iter_pipeline_jobs(manager: ArtifactManager, pipeline_id: str):
    pipeline = manager.project.pipelines.get(pipeline_id)

    try:
        yield from pipeline.jobs.list(iterator=True, include_retried=True)
    except TypeError:
        yield from pipeline.jobs.list(all=True)


def find_previous_job_id(
    manager: ArtifactManager,
    *,
    pipeline_id: str,
    job_name: str,
    current_job_id: int,
) -> t.Optional[int]:
    candidates = []
    for job in _iter_pipeline_jobs(manager, pipeline_id):
        if job.name != job_name:
            continue
        if int(job.id) >= current_job_id:
            continue
        candidates.append(job)

    if not candidates:
        return None

    failed_candidates = [job for job in candidates if job.status == 'failed']
    selected = max(failed_candidates or candidates, key=lambda job: int(job.id))
    return int(selected.id)


def _local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _has_failure(testcase: ET.Element) -> bool:
    return any(_local_name(child.tag) in {'failure', 'error'} for child in testcase)


def collect_failed_junit_names(junit_file: str) -> t.Set[t.Tuple[str, str]]:
    failed_names = set()
    root = ET.parse(junit_file).getroot()
    for testcase in root.iter():
        if _local_name(testcase.tag) != 'testcase':
            continue
        if _has_failure(testcase):
            failed_names.add((testcase.attrib.get('classname', ''), testcase.attrib.get('name', '')))
    return failed_names


def nodeid_to_junit_name(nodeid: str) -> t.Tuple[str, str]:
    path, possible_open_bracket, params = nodeid.partition('[')
    names = path.split('::')
    names[0] = names[0].replace('/', '.')
    if names[0].endswith('.py'):
        names[0] = names[0][:-3]
    names[-1] += possible_open_bracket + params
    return '.'.join(names[:-1]), names[-1]


def app_identity(case) -> t.Tuple[t.Tuple[str, str, str], ...]:
    return tuple((app.path, app.target, app.config) for app in case.apps)


def collect_node_app_map(nodes: t.List[str]) -> t.Dict[str, t.Tuple[t.Tuple[str, str, str], ...]]:
    from idf_ci.idf_pytest import get_pytest_cases

    paths = sorted({node.split('::', 1)[0] for node in nodes})
    cases = get_pytest_cases(paths=paths, marker_expr=None)
    case_map = {case.item.nodeid: app_identity(case) for case in cases}
    return {node: case_map[node] for node in nodes if node in case_map}


def select_retry_nodes(nodes: t.List[str], failed_names: t.Set[t.Tuple[str, str]]) -> t.List[str]:
    failed_nodes = [node for node in nodes if nodeid_to_junit_name(node) in failed_names]
    if not failed_nodes:
        return []

    try:
        node_app_map = collect_node_app_map(nodes)
    except Exception as e:
        LOGGER.warning('Could not collect pytest app metadata: %s. Retrying failed node(s) only.', e)
        return failed_nodes

    failed_apps = set()
    for node in failed_nodes:
        failed_apps.update(node_app_map.get(node, ()))

    if not failed_apps:
        return failed_nodes

    retry_nodes = []
    for node in nodes:
        node_apps = set(node_app_map.get(node, ()))
        if node_apps & failed_apps:
            retry_nodes.append(node)

    return retry_nodes or failed_nodes


def write_nodes(output: str, nodes: t.List[str]) -> None:
    with open(output, 'w', encoding='utf-8') as fw:
        fw.write(' '.join(shlex.quote(node) for node in nodes))


def download_job_artifact(manager: ArtifactManager, job_id: int, artifact_path: str, artifact_dir: str) -> str:
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    output = Path(artifact_dir) / artifact_path
    data = manager.project.jobs.get(job_id).artifact(artifact_path)
    output.write_bytes(data)
    return str(output)


def prepare_retry_app_filter(output: str, artifact_dir: str, nodes_arg: str) -> bool:
    Path(output).write_text('', encoding='utf-8')

    if not _is_job_retry():
        LOGGER.info('Not a retried job. Skipping app retry filter preparation.')
        return False

    nodes = shlex.split(nodes_arg)
    if not nodes:
        LOGGER.warning('No nodes provided. Skipping app retry filter preparation.')
        return False

    current_job_id = os.getenv('CI_JOB_ID')
    job_name = os.getenv('CI_JOB_NAME')
    pipeline_id = os.getenv('CI_PIPELINE_ID')
    if not all([current_job_id, job_name, pipeline_id]):
        LOGGER.warning('Missing GitLab CI variables. Skipping app retry filter preparation.')
        return False

    manager = ArtifactManager()
    previous_job_id = find_previous_job_id(
        manager,
        pipeline_id=pipeline_id,
        job_name=job_name,
        current_job_id=int(current_job_id),
    )
    if previous_job_id is None:
        LOGGER.warning('No previous job attempt found for %s. Skipping app retry filter preparation.', job_name)
        return False

    artifact_path = f'XUNIT_RESULT_{previous_job_id}.xml'
    try:
        junit_file = download_job_artifact(manager, previous_job_id, artifact_path, artifact_dir)
    except Exception as e:
        LOGGER.warning('Could not download %s from job %s: %s', artifact_path, previous_job_id, e)
        return False

    failed_names = collect_failed_junit_names(junit_file)
    if not failed_names:
        LOGGER.warning('No failed pytest cases found in %s. Retrying full job.', artifact_path)
        return False

    retry_nodes = select_retry_nodes(nodes, failed_names)
    if not retry_nodes:
        LOGGER.warning('No retry nodes matched failures from %s. Retrying full job.', artifact_path)
        return False

    write_nodes(output, retry_nodes)
    LOGGER.info('Prepared retry node list from job %s with %d node(s)', previous_job_id, len(retry_nodes))
    return True

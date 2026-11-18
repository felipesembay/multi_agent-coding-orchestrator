import json
from pathlib import Path

import pytest

from orchestrator import core


@pytest.mark.parametrize('entry', ['plan', 'implement', 'review'])
def test_core_graph_matches_frozen_v1_topology(entry):
    snapshot = json.loads((Path(__file__).parents[1] / 'fixtures' / 'legacy_graph_topology.json').read_text())
    graph = core.graph(entry).get_graph()
    assert {'nodes': sorted(graph.nodes),
            'edges': sorted([edge.source, edge.target, edge.conditional] for edge in graph.edges)} == snapshot[entry]

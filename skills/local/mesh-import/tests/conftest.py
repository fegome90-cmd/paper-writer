import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mesh_import.store import MeshStore

FIXTURES = Path(__file__).parent / "fixtures"
MIGRATIONS_DIR = Path(__file__).parent.parent / "workspace" / "migrations"


@pytest.fixture
def sample_xml_path():
    return str(FIXTURES / "sample_desc.xml")


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "mesh.db")


@pytest.fixture
def mesh_store(tmp_db):
    return MeshStore(tmp_db)


@pytest.fixture
def populated_store(mesh_store, sample_xml_path):
    mesh_store.import_xml(sample_xml_path)
    return mesh_store


@pytest.fixture
def populated_db(populated_store, tmp_db):
    return tmp_db

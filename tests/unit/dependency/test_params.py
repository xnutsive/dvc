import yaml

import pytest

from dvc.dependency import DependencyPARAMS, loads_params, loadd_from
from dvc.dependency.param import BadParamFileError, MissingParamsError
from dvc.stage import Stage


PARAMS = {
    "foo": 1,
    "bar": 53.135,
    "baz": "str",
    "qux": None,
}


def test_loads_params(dvc):
    stage = Stage(dvc)
    deps = loads_params(stage, ["foo", "bar,baz", "a_file:qux"])
    assert len(deps) == 2

    assert isinstance(deps[0], DependencyPARAMS)
    assert deps[0].def_path == DependencyPARAMS.DEFAULT_PARAMS_FILE
    assert deps[0].params == ["foo", "bar", "baz"]
    assert deps[0].info == {}

    assert isinstance(deps[1], DependencyPARAMS)
    assert deps[1].def_path == "a_file"
    assert deps[1].params == ["qux"]
    assert deps[1].info == {}


def test_loadd_from(dvc):
    stage = Stage(dvc)
    deps = loadd_from(stage, [{"params": PARAMS}])
    assert len(deps) == 1
    assert isinstance(deps[0], DependencyPARAMS)
    assert deps[0].def_path == DependencyPARAMS.DEFAULT_PARAMS_FILE
    assert deps[0].params == list(PARAMS.keys())
    assert deps[0].info == PARAMS


def test_dumpd_with_info(dvc):
    dep = DependencyPARAMS(Stage(dvc), None, PARAMS)
    assert dep.dumpd() == {
        "path": "params.yaml",
        "params": PARAMS,
    }


def test_dumpd_without_info(dvc):
    dep = DependencyPARAMS(Stage(dvc), None, list(PARAMS.keys()))
    assert dep.dumpd() == {
        "path": "params.yaml",
        "params": list(PARAMS.keys()),
    }


def test_get_info_nonexistent_file(dvc):
    dep = DependencyPARAMS(Stage(dvc), None, ["foo"])
    assert dep._get_info() == {}


def test_get_info_unsupported_format(tmp_dir, dvc):
    tmp_dir.gen("params.yaml", b"\0\1\2\3\4\5\6\7")
    dep = DependencyPARAMS(Stage(dvc), None, ["foo"])
    with pytest.raises(BadParamFileError):
        dep._get_info()


def test_get_info_nested(tmp_dir, dvc):
    tmp_dir.gen(
        "params.yaml", yaml.dump({"some": {"path": {"foo": ["val1", "val2"]}}})
    )
    dep = DependencyPARAMS(Stage(dvc), None, ["some.path.foo"])
    assert dep._get_info() == {"some.path.foo": ["val1", "val2"]}


def test_save_info_missing_params(dvc):
    dep = DependencyPARAMS(Stage(dvc), None, ["foo"])
    with pytest.raises(MissingParamsError):
        dep.save_info()

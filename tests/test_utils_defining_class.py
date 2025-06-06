"""Unit testing for get_defining_class in cmd2/utils.py module."""

import functools

import cmd2.utils as cu


class ParentClass:
    def func_with_overrides(self) -> None:
        pass

    def parent_only_func(self, param1, param2) -> None:
        pass


class ChildClass(ParentClass):
    def func_with_overrides(self) -> None:
        super().func_with_overrides()

    def child_function(self) -> None:
        pass

    def lambda1() -> int:
        return 1

    def lambda2() -> int:
        return 2

    @classmethod
    def class_method(cls) -> None:
        pass

    @staticmethod
    def static_meth() -> None:
        pass


def func_not_in_class() -> None:
    pass


def test_get_defining_class() -> None:
    parent_instance = ParentClass()
    child_instance = ChildClass()

    # validate unbound class functions
    assert cu.get_defining_class(ParentClass.func_with_overrides) is ParentClass
    assert cu.get_defining_class(ParentClass.parent_only_func) is ParentClass
    assert cu.get_defining_class(ChildClass.func_with_overrides) is ChildClass
    assert cu.get_defining_class(ChildClass.parent_only_func) is ParentClass
    assert cu.get_defining_class(ChildClass.child_function) is ChildClass
    assert cu.get_defining_class(ChildClass.class_method) is ChildClass
    assert cu.get_defining_class(ChildClass.static_meth) is ChildClass

    # validate bound class methods
    assert cu.get_defining_class(parent_instance.func_with_overrides) is ParentClass
    assert cu.get_defining_class(parent_instance.parent_only_func) is ParentClass
    assert cu.get_defining_class(child_instance.func_with_overrides) is ChildClass
    assert cu.get_defining_class(child_instance.parent_only_func) is ParentClass
    assert cu.get_defining_class(child_instance.child_function) is ChildClass
    assert cu.get_defining_class(child_instance.class_method) is ChildClass
    assert cu.get_defining_class(child_instance.static_meth) is ChildClass

    # bare functions resolve to nothing
    assert cu.get_defining_class(func_not_in_class) is None

    # lambdas and nested lambdas
    assert cu.get_defining_class(ChildClass.lambda1) is ChildClass
    assert cu.get_defining_class(ChildClass.lambda2) is ChildClass
    assert cu.get_defining_class(ChildClass().lambda1) is ChildClass
    assert cu.get_defining_class(ChildClass().lambda2) is ChildClass

    # partials
    partial_unbound = functools.partial(ParentClass.parent_only_func, 1)
    nested_partial_unbound = functools.partial(partial_unbound, 2)
    assert cu.get_defining_class(partial_unbound) is ParentClass
    assert cu.get_defining_class(nested_partial_unbound) is ParentClass

    partial_bound = functools.partial(parent_instance.parent_only_func, 1)
    nested_partial_bound = functools.partial(partial_bound, 2)
    assert cu.get_defining_class(partial_bound) is ParentClass
    assert cu.get_defining_class(nested_partial_bound) is ParentClass

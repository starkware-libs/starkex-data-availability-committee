from abc import ABC, abstractmethod
from typing import Type, TypeVar

import marshmallow_dataclass

from starkware.starkware_utils.config_base import get_object_by_path
from starkware.starkware_utils.serializable_dataclass import SerializableMarshmallowDataclass
from starkware.starkware_utils.validated_dataclass import ValidatedMarshmallowDataclass

TStateBase = TypeVar("TStateBase", bound="StateBase")


@marshmallow_dataclass.dataclass(frozen=True)
class StateUpdateBase(SerializableMarshmallowDataclass):
    """
    Base class for the State classes.
    Contains the common properties (prev_batch_id) and (abstract) functions for fetching the State
    classes objects and roots.
    """

    prev_batch_id: int

    @property
    def objects(self):
        pass

    @property
    def roots(self):
        pass


class StateBase(ABC):
    @staticmethod
    def get_class_by_path(path: str) -> Type["StateBase"]:
        state_class = get_object_by_path(path=path)
        assert issubclass(state_class, StateBase)
        return state_class

    @classmethod
    @abstractmethod
    def empty(cls: Type[TStateBase]) -> TStateBase:
        """
        Returns an empty state object.
        """


@marshmallow_dataclass.dataclass(frozen=True)
class BatchDataResponseBase(ValidatedMarshmallowDataclass):
    @staticmethod
    def get_class_by_path(path: str) -> Type["BatchDataResponseBase"]:
        response_class = get_object_by_path(path=path)
        assert issubclass(response_class, BatchDataResponseBase)
        return response_class


@marshmallow_dataclass.dataclass(frozen=True)
class CommitteeSignature(ValidatedMarshmallowDataclass):
    """
    The information describing a committee signature.

    :param batch_id: ID of signed batch.
    :type batch_id: int
    :param signature: Committee signature for batch.
    :type signature: str
    :param member_key: Committee member public key used for identification.
    :type member_key: str
    :param claim_hash: Claim hash being signed used for validating the expected claim.
    :type claim_hash: str
    """

    batch_id: int
    signature: str
    member_key: str
    claim_hash: str

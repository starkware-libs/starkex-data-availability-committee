import typing
from dataclasses import field

import marshmallow.fields as mfields
import marshmallow_dataclass
from marshmallow.fields import Boolean, Dict, List, String

from starkware.starkware_utils.config_base import Config
from starkware.starkware_utils.field_validators import (
    validate_absolute_linux_path,
    validate_availability_gateway_endpoint_url,
    validate_certificates_path,
    validate_communication_params,
    validate_positive,
)
from starkware.starkware_utils.marshmallow_dataclass_fields import (
    RequiredBoolean,
    RequiredFloat,
    StrictRequiredInteger,
)

# Default configuration values.

DEFAULT_VALIDATE_ORDERS = False
DEFAULT_VALIDATE_ROLLUP = None
DEFAULT_DUMP_BATCH = False
DEFAULT_FACT_STORAGE_CACHE_SIZE = 65536
DEFAULT_TIMEOUT_IN_SECONDS = 300
DEFAULT_POLLING_INTERVAL = 1.0
DEFAULT_PRIVATE_KEY_PATH = "/private_key.txt"
DEFAULT_STATE_UPDATE_CLASS_PATH = ""
DEFAULT_CERTIFICATES_PATH = None


# Validation functions for configurations.
validate_private_key_path = validate_absolute_linux_path("private_key_path", allow_none=False)


# Configuration schema definition.
@marshmallow_dataclass.dataclass(frozen=True)
class CommitteeConfig(Config):
    availability_gateway_endpoint: str = field(
        metadata=dict(
            marshmallow_field=mfields.String(validate=validate_availability_gateway_endpoint_url),
            description="AvailabilityGateway endpoint",
        )
    )

    polling_interval: float = field(
        metadata=dict(
            marshmallow_field=RequiredFloat(validate=validate_positive("polling_interval")),
            description="Polling interval in seconds",
        ),
        default=DEFAULT_POLLING_INTERVAL,
    )

    validate_orders: bool = field(
        metadata=dict(
            marshmallow_field=RequiredBoolean(), description="Enabler for order validation"
        ),
        default=DEFAULT_VALIDATE_ORDERS,
    )

    validate_rollup: typing.Optional[bool] = field(
        metadata=dict(
            description="Enabler for rollup vault validation. If unset, old API version is used.",
        ),
        default=DEFAULT_VALIDATE_ROLLUP,
    )

    # The value of the following field determines whether the serialized batch is dumped to the
    # committee storage (as a backup) upon invoking custom_validation.is_valid().
    dump_batch: bool = field(
        metadata=dict(marshmallow_field=Boolean(), description="Enabler for batch serialization"),
        default=DEFAULT_DUMP_BATCH,
    )

    committee_objects: typing.List[typing.Dict[str, str]] = field(
        metadata=dict(
            marshmallow_field=List(Dict(keys=String, values=String)),
            description="Paths, tree types and tree heights for committee objects",
        ),
        default_factory=list,
    )

    batch_data_response_class_path: str = field(
        metadata=dict(
            marshmallow_field=String(),
            description="Path of the BatchDataResponse class for the committee",
        ),
        default=DEFAULT_STATE_UPDATE_CLASS_PATH,
    )

    fact_storage_cache_size: int = field(
        metadata=dict(
            marshmallow_field=StrictRequiredInteger(), description="Fact storage cache size"
        ),
        default=DEFAULT_FACT_STORAGE_CACHE_SIZE,
    )

    private_key_path: str = field(
        metadata=dict(
            marshmallow_field=mfields.String(validate=validate_private_key_path),
            description="Path to file containing the private key of the committee member",
        ),
        default=DEFAULT_PRIVATE_KEY_PATH,
    )

    http_request_timeout: int = field(
        metadata=dict(
            marshmallow_field=StrictRequiredInteger(),
            description=("HTTP request timeout in seconds."),
        ),
        default=DEFAULT_TIMEOUT_IN_SECONDS,
    )

    certificates_path: typing.Optional[str] = field(
        metadata=dict(
            marshmallow_field=String(validate=validate_certificates_path, allow_none=True),
            description="Path to the directory containing the certificates",
        ),
        default=DEFAULT_CERTIFICATES_PATH,
    )

    def __post_init__(self):
        super().__post_init__()
        validate_communication_params(
            url=self.availability_gateway_endpoint, certificates_path=self.certificates_path
        )

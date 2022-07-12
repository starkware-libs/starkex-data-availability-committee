python_lib(perpetual_public_business_logic_lib
    PREFIX services/perpetual/public/business_logic

    FILES
    state_objects.py

    LIBS
    perpetual_public_definitions_lib
    starkware_commitment_tree_facts_lib
    starkware_crypto_lib
    starkware_dataclasses_utils_lib
    starkware_error_handling_lib
    starkware_python_utils_lib
    starkware_storage_lib
    starkware_utils_lib
    pip_frozendict
    pip_marshmallow
    pip_marshmallow_dataclass
)

python_lib(perpetual_public_definitions_lib
    PREFIX services/perpetual/public/definitions

    FILES
    constants.py
    error_codes.py
    fields.py

    LIBS
    starkware_crypto_lib
    starkware_dataclasses_utils_lib
    starkware_error_handling_lib
    pip_marshmallow
)

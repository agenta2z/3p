"""
Property-based tests for KeyValue Service.

# Feature: knowledge-service-extraction
# Properties 1-4: KV put/get round-trip, upsert overwrites, batch equals individual,
#                 percent-encoding round-trip

Uses Hypothesis to verify universal correctness properties across
randomly generated inputs. Tests are parametrized across all three backends
(memory, file, sqlite) via the kv_service fixture.
"""

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from python_utils.service_utils.keyvalue_service.file_keyvalue_service import (
    _encode_key,
    _decode_key,
)

from conftest import (
    json_value_strategy,
    key_strategy,
    namespace_strategy,
    kv_items_strategy,
)

# Shared settings for tests that use the kv_service fixture.
# The fixture is not reset between @given iterations, but this is safe
# because all properties hold regardless of pre-existing data in the store
# (put/get uses the same key, upsert overwrites, etc.).
_fixture_settings = settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# Feature: knowledge-service-extraction, Property 1: KV put/get round-trip


class TestKVPutGetRoundTrip:
    """Property 1: KV put/get round-trip.

    For any JSON-serializable Python value, any valid key string, and any
    namespace (including None), putting the value and then getting it with
    the same key and namespace should return an equivalent value.

    **Validates: Requirements 3.1**
    """

    @given(
        key=key_strategy(),
        value=json_value_strategy(),
        namespace=namespace_strategy(),
    )
    @_fixture_settings
    def test_put_get_round_trip(self, kv_service, key, value, namespace):
        """put(key, value, namespace) followed by get(key, namespace) returns
        an equivalent value.

        **Validates: Requirements 3.1**
        """
        kv_service.put(key, value, namespace=namespace)
        retrieved = kv_service.get(key, namespace=namespace)
        assert retrieved == value, (
            f"Round-trip failed: put({key!r}, {value!r}, namespace={namespace!r}) "
            f"then get returned {retrieved!r}"
        )

    @given(
        key=key_strategy(),
        value=json_value_strategy(),
    )
    @_fixture_settings
    def test_put_get_round_trip_default_namespace(self, kv_service, key, value):
        """put/get round-trip works with the default namespace (None).

        **Validates: Requirements 3.1**
        """
        kv_service.put(key, value)
        retrieved = kv_service.get(key)
        assert retrieved == value, (
            f"Round-trip failed with default namespace: "
            f"put({key!r}, {value!r}) then get returned {retrieved!r}"
        )


# Feature: knowledge-service-extraction, Property 2: KV upsert overwrites previous value


class TestKVUpsertOverwrites:
    """Property 2: KV upsert overwrites previous value.

    For any key, namespace, and two distinct JSON-serializable values v1 and v2,
    putting v1 then putting v2 with the same key and namespace should result
    in get returning v2.

    **Validates: Requirements 1.5**
    """

    @given(
        key=key_strategy(),
        v1=json_value_strategy(),
        v2=json_value_strategy(),
        namespace=namespace_strategy(),
    )
    @_fixture_settings
    def test_upsert_overwrites_previous_value(self, kv_service, key, v1, v2, namespace):
        """put(key, v1) then put(key, v2) results in get(key) returning v2.

        **Validates: Requirements 1.5**
        """
        assume(v1 != v2)

        kv_service.put(key, v1, namespace=namespace)
        kv_service.put(key, v2, namespace=namespace)
        retrieved = kv_service.get(key, namespace=namespace)
        assert retrieved == v2, (
            f"Upsert failed: put({key!r}, {v1!r}), put({key!r}, {v2!r}), "
            f"get returned {retrieved!r} instead of {v2!r}"
        )


# Feature: knowledge-service-extraction, Property 3: KV batch operations equal individual operations


class TestKVBatchEqualsIndividual:
    """Property 3: KV batch operations equal individual operations.

    For any dictionary of key-value pairs and any namespace, calling put_many
    followed by get_many should return the same results as calling put and get
    individually for each key.

    **Validates: Requirements 1.2**
    """

    @given(
        items=kv_items_strategy(min_size=1, max_size=10),
        namespace=namespace_strategy(),
    )
    @_fixture_settings
    def test_batch_put_get_equals_individual(self, kv_service, items, namespace):
        """put_many + get_many produces the same results as individual put + get.

        Note: get_many omits keys whose stored value is None (since get()
        returns None for both "not found" and "stored None"). This test
        verifies that batch and individual approaches produce the same
        result under this contract.

        **Validates: Requirements 1.2**
        """
        # Filter out None values from items since get_many cannot
        # distinguish "not found" from "stored None"
        non_none_items = {k: v for k, v in items.items() if v is not None}

        # Batch approach
        kv_service.put_many(items, namespace=namespace)
        batch_result = kv_service.get_many(list(items.keys()), namespace=namespace)

        # Individual approach using get() with the same None-filtering
        individual_result = {}
        for key in items.keys():
            val = kv_service.get(key, namespace=namespace)
            if val is not None:
                individual_result[key] = val

        # Both approaches should agree on non-None values
        assert batch_result == individual_result, (
            f"Batch vs individual mismatch for items={items!r}, "
            f"namespace={namespace!r}:\n"
            f"  batch_result={batch_result!r}\n"
            f"  individual_result={individual_result!r}"
        )

        # Additionally verify that all non-None items are present
        for key, value in non_none_items.items():
            assert key in batch_result, (
                f"Key {key!r} with non-None value missing from batch result"
            )
            assert batch_result[key] == value, (
                f"Value mismatch for key {key!r}: "
                f"expected {value!r}, got {batch_result[key]!r}"
            )


# Feature: knowledge-service-extraction, Property 4: Percent-encoding round-trip


# Strategy that generates strings containing characters from {%, :, /, \}
# plus arbitrary other characters.
_special_chars = st.sampled_from(["%", ":", "/", "\\"])
_any_char = st.characters()


def _percent_encoding_string_strategy():
    """Generate strings that contain at least one character from {%, :, /, \\}
    mixed with arbitrary other characters.

    This ensures the encoding/decoding logic is exercised on the special
    characters that require percent-encoding.
    """
    return st.builds(
        lambda parts: "".join(parts),
        st.lists(
            st.one_of(_special_chars, _any_char),
            min_size=1,
            max_size=50,
        ).filter(lambda chars: any(c in chars for c in ["%", ":", "/", "\\"]))
    )


class TestPercentEncodingRoundTrip:
    """Property 4: Percent-encoding round-trip.

    For any string containing characters from the set {%, :, /, \\} plus
    arbitrary other characters, encoding then decoding should produce the
    original string.

    **Validates: Requirements 2.5**
    """

    @given(s=_percent_encoding_string_strategy())
    @settings(max_examples=200)
    def test_encode_decode_round_trip(self, s):
        """_encode_key(s) followed by _decode_key should return the original string.

        **Validates: Requirements 2.5**
        """
        encoded = _encode_key(s)
        decoded = _decode_key(encoded)
        assert decoded == s, (
            f"Percent-encoding round-trip failed:\n"
            f"  original: {s!r}\n"
            f"  encoded:  {encoded!r}\n"
            f"  decoded:  {decoded!r}"
        )

    @given(s=st.text(min_size=0, max_size=100))
    @settings(max_examples=200)
    def test_encode_decode_round_trip_any_string(self, s):
        """_encode_key(s) followed by _decode_key should return the original
        string for any arbitrary string (not just those with special chars).

        **Validates: Requirements 2.5**
        """
        encoded = _encode_key(s)
        decoded = _decode_key(encoded)
        assert decoded == s, (
            f"Percent-encoding round-trip failed:\n"
            f"  original: {s!r}\n"
            f"  encoded:  {encoded!r}\n"
            f"  decoded:  {decoded!r}"
        )

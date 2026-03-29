# Feature: alert-triage-agent, Property 6: Environment label hierarchical extraction
# **Validates: Requirements 5.1, 5.2, 5.3**

from hypothesis import given, settings, strategies as st
from labelers.environment import extract_environment


# --- Custom Hypothesis Strategies ---


def _env_value():
    """Generate a non-empty environment string."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Pd")),
        min_size=1,
        max_size=30,
    )


def _aws_account_id():
    """Generate a 12-digit AWS account ID."""
    return st.from_regex(r"[0-9]{12}", fullmatch=True)


def _valid_arn(account_id):
    """Build a valid ARN string embedding the given account ID."""
    return f"arn:aws:sns:us-east-1:{account_id}:SomeTopic"


def _env_field_name():
    """Pick one of the recognised explicit environment field names."""
    return st.sampled_from(["environment", "env", "environment_id"])


# --- Message strategies for each tier of the fallback chain ---


def message_with_explicit_env():
    """Messages that carry an explicit environment field at top level.

    Expected result: the explicit env value (highest precedence).
    """
    return _env_field_name().flatmap(
        lambda field: _env_value().flatmap(
            lambda val: st.fixed_dictionaries(
                {field: st.just(val), "extra": st.text(max_size=20)}
            ).map(lambda d: (d, val))
        )
    )


def message_with_nested_env():
    """Messages that carry an explicit environment field inside 'detail'.

    No top-level env field present.
    Expected result: the nested env value.
    """
    return _env_field_name().flatmap(
        lambda field: _env_value().flatmap(
            lambda val: st.fixed_dictionaries(
                {
                    "detail": st.fixed_dictionaries(
                        {field: st.just(val), "status": st.text(max_size=10)}
                    ),
                    "data": st.text(max_size=20),
                }
            ).map(lambda d: (d, val))
        )
    )


def message_with_only_arn():
    """Messages that have no env fields but contain a TopicArn with an account ID.

    Expected result: the account ID extracted from the ARN.
    """
    return _aws_account_id().flatmap(
        lambda acct: st.fixed_dictionaries(
            {
                "TopicArn": st.just(_valid_arn(acct)),
                "Type": st.just("Notification"),
            }
        ).map(lambda d: (d, acct))
    )


def message_with_detail_account_only():
    """Messages with no env fields and no ARN, but detail.account is set.

    Expected result: the detail account value.
    """
    return _aws_account_id().flatmap(
        lambda acct: st.fixed_dictionaries(
            {
                "source": st.just("aws.ec2"),
                "detail-type": st.text(min_size=1, max_size=30),
                "detail": st.fixed_dictionaries(
                    {"account": st.just(acct), "info": st.text(max_size=10)}
                ),
            }
        ).map(lambda d: (d, acct))
    )


def message_with_env_and_arn():
    """Messages that have BOTH an explicit env field AND an ARN.

    Expected result: the explicit env value (env takes precedence over ARN).
    """
    return _env_field_name().flatmap(
        lambda field: st.tuples(_env_value(), _aws_account_id()).flatmap(
            lambda pair: st.fixed_dictionaries(
                {
                    field: st.just(pair[0]),
                    "TopicArn": st.just(_valid_arn(pair[1])),
                    "Type": st.just("Notification"),
                }
            ).map(lambda d: (d, pair[0]))
        )
    )


def message_with_nothing():
    """Messages with no env fields, no ARNs, no detail.account.

    Expected result: "UNKNOWN".
    """
    return st.fixed_dictionaries(
        {
            "id": st.text(min_size=1, max_size=30),
            "data": st.text(min_size=1, max_size=50),
        }
    ).map(lambda d: (d, "UNKNOWN"))


# --- Property Tests ---


@settings(max_examples=100)
@given(data=message_with_explicit_env())
def test_explicit_env_field_returned(data):
    """When a message has an explicit environment field at top level,
    extract_environment returns that value."""
    msg, expected = data
    assert extract_environment(msg) == expected


@settings(max_examples=100)
@given(data=message_with_nested_env())
def test_nested_env_field_returned(data):
    """When a message has an explicit environment field nested in 'detail'
    (and none at top level), extract_environment returns that value."""
    msg, expected = data
    assert extract_environment(msg) == expected


@settings(max_examples=100)
@given(data=message_with_only_arn())
def test_arn_account_id_returned_when_no_env_field(data):
    """When a message has no explicit env fields but contains a TopicArn,
    extract_environment returns the AWS account ID from the ARN."""
    msg, expected = data
    assert extract_environment(msg) == expected


@settings(max_examples=100)
@given(data=message_with_detail_account_only())
def test_detail_account_returned_when_no_env_or_arn(data):
    """When a message has no env fields and no ARN but has detail.account,
    extract_environment returns the detail account value."""
    msg, expected = data
    assert extract_environment(msg) == expected


@settings(max_examples=100)
@given(data=message_with_env_and_arn())
def test_env_field_takes_precedence_over_arn(data):
    """When a message has both an explicit env field and an ARN,
    the explicit env field takes precedence."""
    msg, expected = data
    assert extract_environment(msg) == expected


@settings(max_examples=100)
@given(data=message_with_nothing())
def test_unknown_returned_when_no_env_info(data):
    """When a message has no env fields, no ARNs, and no detail.account,
    extract_environment returns 'UNKNOWN'."""
    msg, expected = data
    assert extract_environment(msg) == expected

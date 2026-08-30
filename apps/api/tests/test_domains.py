from step_by_step_api.auth_states.domains import registrable_domain


def test_registrable_domain_follows_public_suffix_rules() -> None:
    assert registrable_domain("www.example.co.uk") == "example.co.uk"
    assert registrable_domain("app.example.co.uk") == "example.co.uk"
    assert registrable_domain("foo.github.io") == "foo.github.io"

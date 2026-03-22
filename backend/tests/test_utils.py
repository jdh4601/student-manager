from app.utils.grade_calculator import calculate_grade
from app.utils.security import hash_password, verify_password, create_access_token, decode_token


def test_calculate_grade_boundaries():
    assert calculate_grade(100) == 1
    assert calculate_grade(96) == 1
    assert calculate_grade(95.99) == 2
    assert calculate_grade(89) == 2
    assert calculate_grade(88.99) == 3
    assert calculate_grade(0) == 9


def test_password_hash_verify():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_encode_decode_roundtrip():
    token = create_access_token({"sub": "abc", "role": "teacher", "school_id": "sid"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "abc"
    assert payload["role"] == "teacher"
    assert payload["type"] == "access"


from recipes import safe_recipes


def test_user_1_gets_safe_recipes(conn):
    result = safe_recipes(conn, 1)
    names = sorted(name for _id, name in result)
    assert names == ["Paneer bhurji", "Poha"]

def test_user_2_gets_safe_recipes(conn):
    result = safe_recipes(conn, 2)
    names = sorted(name for _id, name in result)
    assert names == ["Peanut chutney sandwich","Poha"]

def test_unknown_user_gets_no_recipes(conn):
    result = safe_recipes(conn, 999)
    names = sorted(name for _id, name in result)
    assert names == []


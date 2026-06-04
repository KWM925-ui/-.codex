from math_bug import add


if __name__ == "__main__":
    result = add(2, 3)
    if result != 5:
        raise SystemExit(f"FAIL: add(2, 3) returned {result}, expected 5")
    print("PASS: add(2, 3) == 5")

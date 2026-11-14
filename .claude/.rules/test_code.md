# Test code rules in "backend/"
## Test file rules
- Put files in "backend/tests/*"
- Mirror the structure of the "app" folder
- Name test files "test_<original file name>.py"
- Write tests with pytest

## Test design rules
- Write service unit tests
- Write repository unit tests
- Write endpoint API tests
- Write 3 or more test cases per function
- Cover both success and failure cases
- Mock external dependencies

## Test function name rules
- Always write test function names in English
- Use the form "test_<original function name>_<success/failed>_with_<test case>" (e.g. `_with_user_not_found`)

## Comment rules
- Always write comments in Korean
- Describe the test case and whether it's a success or failure case in detail
- For each test case, write the test data and the intended result

## Example test comment
```
def test_get_user_info_fail_with_no_user_info():
"""
유저 정보 조회(실패)

입력 데이터
    - user_id = no_user

예상 출력 데이터
    - raise 404 error
"""
```

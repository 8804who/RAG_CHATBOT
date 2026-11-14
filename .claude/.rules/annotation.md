## Comment rules
### Comment rules for non-endpoint functions in "backend/"
- Write every comment in Korean
- Describe the function, its parameters, and its output format
- End the function description in a Korean noun form, like "인가 코드를 토큰으로 교환 후 세션 생성"

### Example: non-endpoint function comment in "backend/"
```
async def login(user_id: str, password: str) -> str
"""
유저 로그인 처리

Parameters:
    user_id(str): 유저 ID
    password(str): 비밀번호

Returns:
    access_token(str): 유저 AccessToken
```

### Comment rules for endpoint functions in "backend/"
- Write every docstring in Korean
- Describe the API's role, Path Variables, Query Variables, Request Body, Response Body, and Error Response format
- Omit sections that don't apply (e.g. Request Body for a GET)
- End the endpoint role description in a Korean noun form, like "유저 가입" (first line of the docstring)

### Example: endpoint function comment in "backend/"
@router.get("/{service_name}")
async def get_user_info(
    service_name: Annotated[str, Path()],
    query: Annotated[GetUserInfoRequest, Query()],
    session: Annotated[Session, Depends(check_session)],
):
    """
    ### 서비스별 유저 정보 조회

    Path Variables:
        service_name(str): 검색할 서비스명

    Query Variables:
        page(int): 조회 페이지 번호
        size(int): 페이지별 조회 유저 수

    Response Body:
        UserInfoList: 유저 정보 목록
            user_id: 유저 ID
            user_name: 유저 이름

    Error Response:
        조회한 서비스가 존재하지 않을 경우: (404 Not Found, "존재하지 않는 서비스입니다.")
        서버 내부 오류 발생 시: (500 Internal Server Error, "일시적으로 장애가 발생하였습니다.")
    """

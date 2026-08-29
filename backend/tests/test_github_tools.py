from app.tools.github_tools import GitHubWriteFileTool, build_github_tools


async def test_build_github_tools_returns_expected_set():
    tools = build_github_tools(lambda: None)
    names = {t.name for t in tools}
    assert {
        "github_search_repos",
        "github_list_files",
        "github_read_file",
        "github_write_file",
        "github_create_issue",
        "github_create_pull_request",
        "github_list_issues",
    } <= names


async def test_write_file_without_token_errors_gracefully():
    tool = GitHubWriteFileTool(lambda: None)
    result = await tool.run(owner="acme", repo="widgets", path="a.txt", content="hi", message="test")
    assert "no github token" in result.lower()


async def test_search_repos_schema_shape():
    tools = build_github_tools(lambda: None)
    search = next(t for t in tools if t.name == "github_search_repos")
    schema = search.schema()
    assert schema["function"]["name"] == "github_search_repos"
    assert "q" in schema["function"]["parameters"]["properties"]

#!/usr/bin/env python3
"""GitHub issue inbox for Grok V1.2 PAPER, read-only.

No issue closing, no GitHub writes, no orders. GitHub author ID is checked,
then every decision is independently checked against an engine-owned snapshot.
"""
import json
import re
import urllib.parse
import urllib.request

REPO="cyrillaferrere/kraken-sim"
LABEL="it-decision"
API="https://api.github.com/repos/"+REPO+"/issues"

class InboxError(RuntimeError):pass

def parse_decision_issue(issue,authorized_user_id):
    if type(authorized_user_id) is not int or authorized_user_id<=0:
        raise InboxError("AUTHORIZED_GROK_AUTHOR_ID_REQUIRED")
    if not isinstance(issue,dict) or issue.get("pull_request") or issue.get("state")!="open":
        raise InboxError("NOT_OPEN_ISSUE")
    if issue.get("user",{}).get("id")!=authorized_user_id:
        raise InboxError("UNAUTHORIZED_ISSUE_AUTHOR")
    if LABEL not in {label.get("name") for label in issue.get("labels",[]) if isinstance(label,dict)}:
        raise InboxError("IT_DECISION_LABEL_REQUIRED")
    if not str(issue.get("title","")).startswith("IT V1.2 "):
        raise InboxError("INVALID_IT_TITLE")
    body=issue.get("body")
    if not isinstance(body,str) or len(body.encode("utf8"))>8192:
        raise InboxError("ISSUE_BODY_TOO_LARGE")
    fence=chr(96)*3
    body=body.strip()
    if body.startswith(fence+"json"):
        if not body.endswith(fence):raise InboxError("UNCLOSED_JSON_BLOCK")
        body=body[len(fence+"json"): -len(fence)].strip()
    try:
        batch=json.loads(body)
    except ValueError as exc:
        raise InboxError("INVALID_JSON_BATCH") from exc
    if not isinstance(batch,dict) or set(batch)!={"it_id","synthesis_sha256","decisions"}:
        raise InboxError("INVALID_BATCH_KEYS")
    if not isinstance(batch["synthesis_sha256"],str) or not re.fullmatch("[a-f0-9]{64}",batch["synthesis_sha256"]):
        raise InboxError("INVALID_SYNTHESIS_SHA256")
    if not isinstance(batch["decisions"],list) or len(batch["decisions"])>20:
        raise InboxError("INVALID_DECISION_COUNT")
    if type(issue.get("number")) is not int:
        raise InboxError("MISSING_ISSUE_NUMBER")
    return {"issue_number":issue["number"],"batch":batch}

def fetch_latest(authorized_user_id,token,opener=None):
    """Return latest valid IT, or None. No GitHub write permissions necessary."""
    if not token:raise InboxError("GITHUB_READ_TOKEN_REQUIRED")
    if type(authorized_user_id) is not int or authorized_user_id<=0:
        raise InboxError("AUTHORIZED_GROK_AUTHOR_ID_REQUIRED")
    query=urllib.parse.urlencode({"state":"open","labels":LABEL,
                                   "sort":"created","direction":"desc","per_page":40})
    url=API+"?"+query
    if opener is None:
        def opener(request):
            with urllib.request.urlopen(request,timeout=15) as response:
                if response.status!=200:raise InboxError("GITHUB_HTTP_ERROR")
                return response.read(250001)
    request=urllib.request.Request(url,headers={
        "Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"KrakenSimPaperV12/1.0"})
    try:
        raw=opener(request)
        if len(raw)>250000:raise InboxError("GITHUB_RESPONSE_OVERSIZE")
        issues=json.loads(raw)
    except (OSError,ValueError,TypeError) as exc:
        raise InboxError("GITHUB_ISSUES_READ_FAILED") from exc
    if not isinstance(issues,list):raise InboxError("GITHUB_ISSUES_INVALID")
    for issue in issues:
        if issue.get("user",{}).get("id")!=authorized_user_id:continue
        try:return parse_decision_issue(issue,authorized_user_id)
        except InboxError:continue
    return None

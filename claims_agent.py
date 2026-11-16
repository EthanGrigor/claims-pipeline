from pathlib import Path

from typing import Literal
from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel


class CostItem(BaseModel):
    item: str
    amount: float


class Claim(BaseModel):
    claimant_name: str | None
    policy_number: str | None
    incident_date: str | None
    claim_submitted_date: str | None
    incident_type: str | None
    description: str
    amount_claimed: float | None
    cost_items: list[CostItem]
    currency: str | None
    missing_information: list[str]


class PolicyCheck(BaseModel):
    coverage_status: Literal["covered", "partially_covered", "not_covered", "unclear"]
    cover_clause: str | None
    excess: float | None
    covered_amount: float | None
    excluded_items: list[str]
    outstanding_requirements: list[str]
    payable_amount: float | None
    reasoning: str


def decide(policy_check):
    if policy_check.coverage_status == "not_covered":
        return "reject"
    elif policy_check.coverage_status == "unclear":
        return "needs_more_information"
    elif policy_check.payable_amount is None:
        return "needs_more_information"
    elif len(policy_check.outstanding_requirements) > 0:
        return "approve_subject_to_evidence"
    else:
        return "approve"


load_dotenv()
client = Anthropic()


instructions = """You are a claims handler at a UK home insurer.
Extract the key details from the customer's claim.
Reply with JSON only, with no other text, using exactly these fields:
claimant_name, policy_number, incident_date, claim_submitted_date, incident_type, description,
amount_claimed, cost_items, currency, missing_information.
Use null for anything the claim does not state.
missing_information is a list of anything a claims handler would still need.
cost_items is a list of each separate cost the claimant mentions, each with an item and an amount."""


check_instructions = """You are a claims handler at a UK home insurer.
You will be given a policy and the details of a claim.
Decide whether the claim is covered under the policy, quoting clause numbers.
Reply with JSON only, with no other text, using exactly these fields:
coverage_status, cover_clause, excess, covered_amount, excluded_items,
outstanding_requirements, payable_amount, reasoning.
coverage_status must be one of: covered, partially_covered, not_covered, unclear.
cover_clause is the single clause under which the claim is covered, for example "1.1", or null if none applies.
covered_amount is the total covered before the excess.
payable_amount is covered_amount minus the excess.
Always give a provisional covered_amount and payable_amount using the amounts claimed, applying any limits and the excess, even if quotes or receipts still need to be verified.
Use null for an amount only if it cannot be calculated at all, for example because cover depends on facts not yet known.
Draw reasonable inferences from the claimant's account, and do not suggest alternative causes the claim gives no reason to suspect.
If coverage_status is not_covered, set excess, covered_amount and payable_amount to 0.
In outstanding_requirements, list only evidence needed to decide or pay this claim. Do not ask for details the insurer already holds on the policy record, such as the policyholder's address, contact details or what the policy covers.
Base your decision only on the policy wording provided."""


def clean_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```")
        text = text.removesuffix("```")
    return text.strip()


def extract_claim(claim_path):
    claim_text = Path(claim_path).read_text(encoding="utf-8")
    response = client.messages.create(
        model="claude-haiku-5-5",
        max_tokens=2000,
        system=instructions,
        messages=[{"role": "user", "content": claim_text}],
    )
    reply_text = response.content[-1].text
    return Claim.model_validate_json(clean_json(reply_text))


def check_policy(claim, policy_path):
    policy_text = Path(policy_path).read_text(encoding="utf-8")
    check_message = f"""Policy:
{policy_text}

Claim details:
{claim.model_dump_json(indent=2)}"""
    check_response = client.messages.create(
        model="claude-haiku-5-5",
        max_tokens=2000,
        system=check_instructions,
        messages=[{"role": "user", "content": check_message}],
    )
    return PolicyCheck.model_validate_json(clean_json(check_response.content[-1].text))


def money(amount):
    if amount is None:
        return "not determined"
    return f"£{amount:,.2f}"


def print_summary(claim, check, decision):
    print()
    print("=" * 60)
    print(f"Claimant:      {claim.claimant_name} ({claim.policy_number})")
    print(f"Decision:      {decision}")
    print(f"Cover clause:  {check.cover_clause}")
    print(f"Claimed:       {money(claim.amount_claimed)}")
    print(f"Covered:       {money(check.covered_amount)}")
    print(f"Excess:        {money(check.excess)}")
    if check.coverage_status == "unclear":
        print(f"Payable:       {money(check.payable_amount)} (only if cover is confirmed)")
    else:
        print(f"Payable:       {money(check.payable_amount)}")
    print("Excluded:")
    for item in check.excluded_items:
        print(f"  - {item}")
    print("Evidence Needed:")
    for item in check.outstanding_requirements:
        print(f"  - {item}")
    print("Reasoning:")
    print(f"  {check.reasoning}")
    print("=" * 60)


test_cases = [
    {"file": "claims/claim_01.txt", "decision": "approve_subject_to_evidence", "payable": 2120},
    {"file": "claims/claim_02.txt", "decision": "reject", "payable": 0},
    {"file": "claims/claim_03.txt", "decision": "needs_more_information", "payable": None},
    {"file": "claims/claim_04.txt", "decision": "approve_subject_to_evidence", "payable": 2300},
]

passed = 0

for case in test_cases:
    claim = extract_claim(case["file"])
    check = check_policy(claim, "policies/home_policy.txt")
    decision = decide(check)
    print_summary(claim, check, decision)

    decision_ok = decision == case["decision"]
    payable_ok = case["payable"] is None or check.payable_amount == case["payable"]

    if decision_ok and payable_ok:
        passed = passed + 1
        print(f"TEST PASSED: {case['file']}")
    else:
        print(f"TEST FAILED: {case['file']} (expected {case['decision']}, {case['payable']}; got {decision}, {check.payable_amount})")

print(f"{passed} of {len(test_cases)} tests passed")



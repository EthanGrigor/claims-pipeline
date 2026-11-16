# Claims Processing Agent (prototype)
This is a claims processing prototype that can read a free-text home insurance claim, check it against a policy and recommend a decision. Built as a learning project. This is a fixed workflow where the code decides the order of the steps, and the model handles the reading and judgement within each one.


## How it works

There are 3 stages: extraction, policy check and decision. The first 2 stages use an LLM, while the third uses Python rules. 

- Extraction sends the free-text claim to an LLM with a schema to fill out with set information, name/date/policy number etc. 

- Policy check sends the policy wording plus the extracted claim details to the model for it to fill out another schema. This schema includes features such as: is the claim covered/partially covered/not covered/unclear, the cover clause, the amount covered, any excluded items, the excess and the amount payable, and the reasoning for the above. 

- The decision step compares the coverage status, the payable amount and whether evidence is outstanding to a fixed set of rules to determine the outcome. 

## Design decisions

- Fields allow `None` to enable a null response from the model to say "not stated" instead of guessing and providing an incorrect response.

- Every models output is validated against the schema before using it. This was so that malformed/incomplete output (such as the cut-off reply, or json wrapped in markdown code fences) stops the program before it can reach the decision.

- The final decision (decision step) was made using deterministic rules so the final decision is predictable and auditable.

- The `cost_items` field was added after finding out information was lost between steps 1 and 2. This records each cost separately, such that the policy check can see each individual coist (i.e. plumber's invoice) and can include or exclude it.

- The `money()` function was added to prevent the program from crashing when an amount is unknown. It allows the display of "not determined", instead of a misleading £0.

- The `if check.coverage_status` was added so that when cover is unclear, the payables figure is labelled "only if cover is confirmed", so a provisional amoun is not mistaken for an agreed one.


## Results

Four test cases were added to check whether the decision and the payable amount (excluding the undetermined amount in claim 3) for each of the claims aligned with my own. If both aligned with mine, "TEST PASSED" is displayed with a total count at the end for how many out of 4 passed. The 4 claims were designed to test different aspects:

- Claim 1: a burst pipe. This has a partial exclusion (£180 plumber's invoice under 4.2) and the water excess.

- Claim 2: a theft with no forced entry. Should be rejected under 1.3.

- Claim 3: a burst tank found after ~2 months away. Cover depends on the 60-day unoccupancy exclusion. This should result in needing more information.

- Claim 4: storm damage. This tests the £1,500 single-item limit, and whether the model can correctly apply the £100 excess instead of the £350 water excess.

Across 4 consecutive runs after the final changes, 16/16 test cases matched my expected answers. On an earlier test run, a crash occurred because the model wrapped its JSON in markdown code fences, which `clean_json` now handles.

## Limitations

The test set used is small and there is only one simplified policy.

The evidence list can vary between runs and, rarely, still asks for information the insurer would already hold (once in the last 4 runs).

The reasoning can sometimes contain errors even when the decision is correct (e.g. stating that a £1,800 repair was within the £1,500 single-item limit, which applies only to contents). 

Currently, there is no evidence tracking, so most approvals are "subject to evidence".

## Possible improvements

- Add more test cases and policies, specifically including more complex policies. 

- Add evidence tracking.

- Use the API’s tool-use feature to enforce the output schema directly, rather than requesting JSON in the prompt, so the format cannot drift.

- Add a human-review flag: the model can mark a claim for review with a reason, and deterministic rules also route all rejections, unclear cases and high-value claims to a person.

## How to run

Requires Python 3.10+ and an Anthropic API key.

```
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a file called `.env` containing:

```
ANTHROPIC_API_KEY=your-key-here
```

Then run:

```
python claims_agent.py
```

This processes the four sample claims in `claims/` against `policies/home_policy.txt` and reports how many match the expected decisions.
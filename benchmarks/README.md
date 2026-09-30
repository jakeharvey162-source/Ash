# Ash comparative task benchmark

Status: not run against authenticated Ash, Manus or Lovable sessions. Do not infer a winner from build checks or marketing claims.

Run each prompt in a fresh project with the same inputs. Record product/version, plan, date, elapsed time, credits/cost, output URL/files, interventions and evidence. Use the same follow-up once per product. Mark unavailable tasks BLOCKED, not FAIL. Repeat three times before drawing a comparative conclusion.

## Shared website task

Build a responsive website for a fictional Johannesburg coffee shop called Ember & Oak. Include a menu filter (coffee/food/all), prices in rand, an accessible mobile menu, light/dark mode that persists after reload, and a booking form with required name, email, date and party size. Store bookings locally for this demo and explicitly label that no booking is sent to the business. No fabricated reviews or awards. Provide runnable source and setup instructions.

Checks: all filters work; invalid booking rejected; valid booking stored across reload; no false confirmation of external sending; keyboard navigation works; no horizontal overflow at 360px; no uncaught console errors; production build passes.

Follow-up: Add cancellation of a saved booking without breaking filtering, theme persistence or form validation.

## Shared application task

Build a student expense tracker with add/edit/delete, amount and date validation, categories, monthly totals, category filtering, local persistence and CSV export. Use these initial entries: Transport R120, Food R85.50, Data R49.99. Show R255.49 total. Explain that local storage is not cloud sync. Provide runnable source.

Checks: exact total; edits update totals; deleting affects only chosen entry; reload preserves data; filtered totals are labelled; CSV quotes commas and quotes correctly; user-entered text renders as text, never executable HTML.

Follow-up: Add a monthly budget and remaining balance, preserving existing saved entries.

## Research task (Ash versus Manus)

Find three currently open virtual hackathons allowing a solo student based in South Africa. Give official registration links, exact closing dates/time zones, eligibility, team-size rules and prize conditions. If fewer than three can be verified, say so rather than inventing an event.

Checks: each factual eligibility/date/prize claim supported by the linked official source; closed events excluded; travel funding never assumed; unavailable information labelled. Independently verify at execution time.

## Scoring

Report passed/total applicable checks, completion time, cost and intervention count separately. A fallback that omits requested functionality fails those checks even if it compiles. A source URL alone does not prove a research claim. Compare Lovable primarily on the shared website/application tasks; do not assign it a general-agent score from untested tasks.

## Current evidence

Local regression checks: 13 Python builder/remote-worker tests passed; Vite production build passed. Local Node was 24.19.0 while the deployment declares 22.x, so CI on Node 22 remains necessary. Authenticated product tasks and comparative scoring are pending.

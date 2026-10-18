# TokenBot collaboration rules

- After every development pass, append a development log to the existing Google Doc titled “Tokenbot 开发计划”: date, concrete changes, validation evidence, unfinished items, and next steps. The private document URL is in the user's task context/memory. Preserve existing content. Never publish credentials or customer payloads to the doc or repository.
- Keep automated inference tests separate from the analysis model. The user requests GPT-6 Astra / high for analysis and modifications; use explicitly selected economical models such as gpt-6.1-sol / low for synthetic live probes. Do not change the user's everyday client configuration merely to run a probe. Restore any temporary setting you actually change.
- Finite live tests need a maximum duration and must stop on failure. Record actual responses, completion events and token usage. A started test is not a passed test; overseas or fixed-question probes do not establish domestic Windows end-to-end reliability.
- Issue distinct client credentials and private handoffs. Never reuse the partner's key across customers. Shared upstream capacity does not mean shared usage records or shared pool selection.
- Work within this thread; do not create or delegate to other agents/tasks unless the user explicitly requests it.

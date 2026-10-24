# Forecasting Job Titles and JD Changes

Forecasts must rest on observable signals. Each prediction lists its signals, the earliest date seen, and a confidence level.

## Leading indicators (strongest first)
1. **New titles in live postings.** A title appearing at several unrelated employers within 6-12 months. Count them.
2. **Preferred → required drift.** A skill listed as "nice to have" in older postings and "required" in recent ones for the same title. Compare postings by date.
3. **Big-employer org moves.** New executive titles (e.g. Chief AI Officer), reorgs, or new teams announced in earnings calls, 10-Ks, press releases, or engineering blogs. Large employers set title norms others copy.
4. **Regulation with deadlines.** Laws or standards that force new accountabilities (AI governance, model risk, data residency). Roles follow compliance dates.
5. **Tooling maturity.** When a technology gets managed cloud services, a CNCF/Linux Foundation project, or vendor certifications, it shifts from specialist niche to mainstream requirement within ~1-2 years.
6. **Survey and posting-data reports.** WEF, LinkedIn, Indeed Hiring Lab, Lightcast, Stanford AI Index trends on skills and titles.
7. **Conference and community signals.** Talk tracks at major industry conferences, new certifications, new O*NET emerging tasks. Weakest; corroborate.

## Confidence rubric
- **High:** 3+ independent signal types, including live postings at multiple employers and a Tier 1 source.
- **Medium:** 2 signal types, or strong posting evidence without macro corroboration.
- **Low:** single signal type or early/anecdotal evidence. Include only if relevant to the person, clearly labeled.

## Patterns worth checking
- **Specialization split:** a broad title fragments into specialist titles as the field matures (e.g. "DevOps" → platform, SRE, developer experience).
- **Consolidation:** adjacent roles merge when tools automate the seams between them.
- **Prefix wave:** an existing title gains a technology prefix ("AI", "ML", "Agent") before settling into a distinct role or dropping the prefix once the skill is assumed.
- **Accountability roles:** new risk/governance/safety titles emerge when a technology hits regulated industries.
- **Automation pressure:** tasks that are repetitive, well-specified, and text- or code-based shrink first. Check O*NET task lists against current automation capabilities.

## Writing the forecast
For each item:
```
**[Title or change]** · Confidence: [H/M/L] · Horizon: [12/24/36 mo]
Signals: [signal 1 + citation], [signal 2 + citation]
Fit for you: [why, tied to resume]
Watch for: [what would confirm or kill this forecast]
```
"Watch for" makes the forecast testable. Skip any forecast where no signal can be cited.

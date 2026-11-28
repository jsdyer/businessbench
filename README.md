# Business Bench

<!-- coolcode:guide -->
Choose a Canadian industry and region, then enter annual revenue and expenses to compare a profit margin privately. In 2024, the 7,546 businesses in the photographic services cohort averaged $142,100 in revenue and $49,300 in net profit. Open a profile for quality grades, revenue quartiles and the original ISED files. Compare standard incorporation fees for a numbered or named company federally, in British Columbia, Ontario or Nova Scotia.
<!-- /coolcode:guide -->

[Open Business Bench](https://coolcode.ca/businessbench/) · [Browse industry profiles](https://coolcode.ca/businessbench/records/) · [Download the financial data](https://coolcode.ca/businessbench/data/benchmarks.csv)

## What the figures mean

Statistics Canada produces Financial Performance Data using business tax returns. Innovation, Science and Economic Development Canada (ISED) publishes the annual editions. Business Bench uses the combined incorporated and unincorporated category and the $30,000 to $5 million annual revenue range. It includes Canada, published provinces and territories, and combined geographic groups. Dollar amounts are means in CAD. The source files express them in thousands. [2024 source catalogue](https://open.canada.ca/data/en/dataset/3f9e1080-4a08-4c0f-ace7-1b94a1afd61d) · [Data dictionary](https://ised-isde.canada.ca/site/ised/sites/default/files/documents/fpd-dpf-data_dictionary_2022.txt) · [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada)

A national industry earns a profile when the source supplies a business count and mean revenue. Other regional results use the same inclusion rule. Identical published NAICS levels with the same industry name, coverage and financial values share a profile. Search accepts their equivalent codes. NAICS levels, Canada, its provinces and the combined regions overlap. Summing those business counts would double count businesses. A missing or withheld amount appears as unavailable. A–E grades on mean estimates describe imputation, with E denoting “use with caution.” Each quartile figure is mean annual revenue for the corresponding quarter of businesses ranked by revenue.

The private calculator divides the visitor’s profit (revenue less expenses) by revenue. Its peer margin divides ISED’s published mean net profit by mean revenue for the selected cohort. Independently rounded figures may differ from subtracting the displayed means. The percentage of profitable businesses is a separate published measure. Visitors’ financial inputs remain in memory and have no submission names, analytics events or storage. The selected geography can be shared using the public `?area=` parameter. Standard CoolCode metrics record ordinary page activity.

The project publishes one self-canonical, readable HTML page per industry, along with an HTML directory, child sitemap and a full CSV. National figures, the regional summary, source references and links to related profiles work with JavaScript disabled. CSV blanks represent unavailable values. Quality columns apply to the immediately preceding amount.

## Incorporation filing fees

[Compare incorporation fees](https://coolcode.ca/businessbench/fees.html) for ordinary for-profit share companies in four jurisdictions. The comparison separates the basic filing from name searches and identifies supplier-priced reports. Service charges, annual filing costs and extra-provincial registrations fall outside the totals. Private quote entries remain in the tab. Each row links to the registry. To refresh the fee page, verify those links, edit the amounts in cents in `config/incorporation-fees.json`, and set its review date to the actual date of that check. This editorial review runs separately from the ISED collector.

## When it updates

On the seventh day of each month at **11:19 UTC**, the refresh workflow checks the federal open-data catalogue for the latest ISED annual edition. It fetches the matching NAICS descriptions, revenue, expenses and profitable-business files, checks their headings, cohort definitions and values, then builds the profiles before committing. The `checked_at` date advances on a successful check even if ISED is still publishing the same reference year. The home page, profiles and `data/status.json` expose the source-check date and reference year separately. Schema changes and incomplete releases fail the workflow before a replacement can be deployed. Pages builds read the validated repository snapshot and run on changes to main or an explicit dispatch.

## Expand or customize

Edit `config/profiles.json` to change the welcome example or related industry links. Use current profile codes from the directory. The industry finder accepts all codes in the saved edition. To add a financial indicator, verify its exact bilingual CSV heading and unit against the official dictionary, extend the collector’s extracted fields and update the report, CSV and tests together. The collector decompresses no upstream archives, accepts only bounded HTTPS downloads from the publisher and keeps compact, deterministic compressed JSON shards under `data/<year>/`. Earlier editions remain available in the repository after annual rollover.

```sh
# Optional source check. Ordinary builds are offline.
python collectors/ised.py
node --test tests/*.test.mjs
python -m unittest discover -s tests -v
python scripts/build.py
python -m http.server 8000 --directory dist
```

For browser QA install `tests/browser-requirements.txt` with pip, run `python -m playwright install chromium`, then `python tests/browser_smoke.py`. Pull requests build and test the site. A successful main-branch Pages workflow deploys the checked build. A separate weekly allowlisted workflow guard and the CoolCode external watchdog cover the monthly collector.

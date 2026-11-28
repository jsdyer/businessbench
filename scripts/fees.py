"""Create a static, accessible fee comparison from separately reviewed registry fees."""
from datetime import date
from html import escape


def amount(cents):
    return f"${cents / 100:,.2f}"


def comparison(config):
    reviewed = date.fromisoformat(config["reviewed"])
    rows = []
    options = []
    for entry in config["jurisdictions"]:
        name = escape(entry["name"])
        filing = entry["filing"]
        word = entry["word_name"]
        if type(filing) is not int or filing <= 0 or (word is not None and (type(word) is not int or word < 0)):
            raise ValueError("Registry fees must use non-negative whole cents")
        word_total = (amount(filing) + " + supplier quote") if word is None else amount(filing + word)
        sources = " · ".join(
            f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'
            for label, url in entry["sources"]
        )
        options.append(f'<option data-filing="{filing}" data-name="{"" if word is None else word}">{name}</option>')
        rows.append(f'<article class="fee-row"><h3>{name}</h3><dl><div><dt>Numbered company</dt><dd>{amount(filing)}</dd></div>'
                    f'<div><dt>Word name</dt><dd>{word_total}</dd></div></dl><p>{escape(entry["note"])}</p><p>{sources}</p></article>')
    return f"""
<h1>What does it cost to incorporate a business?</h1>
<p class="lead">Compare standard filing and company name fees in Canadian dollars. Choose a jurisdiction and name type to estimate the upfront cost of an ordinary for-profit share corporation.</p>
<p data-coolcode-commitments><small>No CoolCode account · No ads · <a href="/about/#our-commitments">How CoolCode works</a></small></p>
<div class="filters interactive"><h2>Estimate your filing costs</h2>
<label for="registry">Where will you incorporate?</label><select id="registry">{''.join(options)}</select>
<label for="kind">Company name</label><select id="kind"><option value="numbered">Assigned company number</option><option value="word">Chosen word name</option></select>
<label for="quote" id="quote-label" hidden>Supplier’s name search quote (CAD)<input id="quote" type="text" inputmode="decimal" placeholder="e.g. 25.00"></label>
<p id="fee-answer" role="status"></p></div>
<h2>Numbered and named companies compared</h2><p>Amounts cover the basic filing and the name search described for each jurisdiction. Budget separately for transaction charges, optional priority processing, professional help, ongoing filings and registrations in other provinces or territories.</p>
<p>Registry fee pages reviewed <time datetime="{reviewed.isoformat()}">{reviewed:%B %d, %Y}</time>.</p>
<div class="fees">{''.join(rows)}</div>
<h2>Where will you operate?</h2><p>A federal filing covers incorporation. Check the province or territory where you will carry on business for any further registration steps and fees. <a href="https://ised-isde.canada.ca/site/corporations-canada/en/register-federal-corporation-province-or-territory">Provincial and territorial registration guidance</a>.</p>
<p><a href="./records/">Compare Canadian small-business financial profiles by industry</a></p>
<script type="module" src="./fees.mjs"></script>"""

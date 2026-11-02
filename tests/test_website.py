import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/KimTholstorf/rvtools-skill"


class LandingPage(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.ids = []
        self.codes = {}
        self.visible = []
        self.hidden = 0
        self.code_id = None
        self.features = {}
        self.feature_id = None
        self.examples = {}
        self.example_id = None
        self.example_code = False
        self.example_metadata = {}
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        self.elements.append((tag, attributes))
        if "id" in attributes:
            self.ids.append(attributes["id"])
        if tag in ("script", "style"):
            self.hidden += 1
        if tag == "code" and "id" in attributes:
            self.code_id = attributes["id"]
            self.codes[self.code_id] = ""
        if tag == "li" and "data-readme-feature" in attributes:
            self.feature_id = attributes["data-readme-feature"]
            self.features[self.feature_id] = ""
        if tag == "li" and "data-readme-example" in attributes:
            self.example_id = attributes["data-readme-example"]
            self.examples[self.example_id] = ""
            self.example_metadata[self.example_id] = {"platform": attributes.get("data-platform"), "pre": False, "code": False}
        if self.example_id and tag in ("pre", "code"):
            self.example_metadata[self.example_id][tag] = True
            if tag == "code":
                self.example_code = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden -= 1
        if tag == "code":
            self.code_id = None
            self.example_code = False
        if tag == "li":
            self.feature_id = None
            self.example_id = None

    def handle_data(self, value):
        if not self.hidden:
            self.visible.append(value)
        if self.code_id:
            self.codes[self.code_id] += value
        if self.feature_id:
            self.features[self.feature_id] += value
        if self.example_id and self.example_code:
            self.examples[self.example_id] += value


class WebsiteTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "web/index.html"
        self.assertTrue(self.path.is_file(), "The analyzer landing page must exist")
        self.html = self.path.read_text(encoding="utf-8")
        self.page = LandingPage(self.html)

    def test_page_is_a_concise_accessible_document_for_the_custom_domain(self):
        tags = [tag for tag, _ in self.page.elements]
        self.assertIn("main", tags)
        self.assertEqual(tags.count("h1"), 1)
        self.assertEqual(len(self.page.ids), len(set(self.page.ids)))
        # Includes examples inside the collapsed "More examples" disclosure.
        self.assertLess(len(" ".join(self.page.visible).split()), 1000)
        self.assertTrue(any(tag == "html" and attrs.get("lang") == "en"
                            for tag, attrs in self.page.elements))
        self.assertTrue(any(tag == "link" and attrs.get("rel") == "canonical"
                            and attrs.get("href") == "https://analyzer.rvtools.help/"
                            for tag, attrs in self.page.elements))
        self.assertTrue(any(tag == "meta" and attrs.get("name") == "viewport"
                            for tag, attrs in self.page.elements))

    def test_cli_commands_match_the_readme_and_copy_targets_exist(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for command_id, expected in {
            "codex-install": (
                "codex plugin marketplace add KimTholstorf/rvtools-skill",
                "codex plugin add rvtools-analyzer@rvtools-analyzer",
            ),
            "claude-install": (
                "claude plugin marketplace add KimTholstorf/rvtools-skill",
                "claude plugin install rvtools@rvtools-analyzer",
            ),
        }.items():
            self.assertEqual(self.page.codes[command_id].strip().splitlines(), list(expected))
            for command in expected:
                self.assertIn(command, readme)
        buttons = [attrs for tag, attrs in self.page.elements if tag == "button"]
        self.assertEqual({item["data-copy"] for item in buttons}, {"codex-install", "claude-install"})
        self.assertTrue(all(item.get("aria-label") for item in buttons))

    def test_grouped_capabilities_preserve_every_readme_bullet_and_source_link(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("## What it can do\n", 1)[1].split("\n## ", 1)[0]
        bullets = [line[2:] for line in section.splitlines() if line.startswith("- ")]
        self.assertEqual(set(self.page.features), {str(i) for i in range(1, len(bullets) + 1)})
        links = {attrs.get("href") for tag, attrs in self.page.elements if tag == "a"}
        for index, bullet in enumerate(bullets, start=1):
            with self.subTest(bullet=index):
                expected = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", bullet)
                self.assertEqual(" ".join(self.page.features[str(index)].split()), expected)
                for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", bullet):
                    self.assertIn(target, links)

    def test_chat_packages_precede_coding_agent_installation(self):
        self.assertLess(self.page.ids.index("downloads"), self.page.ids.index("install"))

    def test_readme_examples_follow_installation_with_more_examples_collapsed(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Examples\n", 1)[1].split("\n## ", 1)[0]
        expected = {str(i): line[2:] for i, line in enumerate(
            (line for line in section.splitlines() if line.startswith("- ")), start=1
        )}
        self.assertEqual(set(self.page.examples), set(expected))
        invocations = {
            "codex": "$rvtools-analyzer ",
            "claude-code": "/rvtools:analyze ",
            "chatgpt-desktop": "@RVTools Analyzer Desktop ",
            "chatgpt-cloud": "@RVTools Analyzer ",
        }
        self.assertEqual({meta["platform"] for meta in self.page.example_metadata.values()}, set(invocations))
        for key, prompt in expected.items():
            with self.subTest(example=key):
                meta = self.page.example_metadata[key]
                self.assertTrue(meta["pre"] and meta["code"], "Each prompt must use a pre/code block")
                prefix = invocations[meta["platform"]]
                self.assertEqual(" ".join(self.page.examples[key].split()), prefix + prompt.strip("“”"))
        sections = [attrs.get("aria-labelledby") for tag, attrs in self.page.elements if tag == "section"]
        self.assertEqual(sections[sections.index("install") + 1], "usage-examples")
        disclosures = [attrs for tag, attrs in self.page.elements if tag == "details"]
        self.assertEqual(len(disclosures), 1)
        self.assertNotIn("open", disclosures[0])

    def test_header_has_reference_gutters_without_a_centered_brand_or_icon(self):
        header = self.html.split("<header>", 1)[1].split("</header>", 1)[0]
        self.assertNotIn("<svg", header)
        inner = re.search(r"\.header-inner\s*\{([^}]+)\}", self.html).group(1)
        self.assertNotIn("max-width", inner)
        self.assertNotIn("margin: auto", inner)

    def test_claude_skill_keeps_a_release_fallback_without_pinning_a_version(self):
        downloads = [attrs for tag, attrs in self.page.elements if tag == "a" and "data-package" in attrs]
        self.assertEqual({attrs["data-package"] for attrs in downloads}, {
            "rvtools-skill-",
        })
        for attrs in downloads:
            self.assertEqual(attrs["href"], REPOSITORY + "/releases/latest")
        self.assertNotRegex(self.html, r"rvtools-(?:chatgpt-[a-z]+|skill)-\d+\.\d+\.\d+")
        self.assertIn("https://api.github.com/repos/KimTholstorf/rvtools-skill/releases/latest", self.html)

    def test_chatgpt_links_point_to_publication_notice_at_the_bottom(self):
        buttons = [attrs for tag, attrs in self.page.elements
                   if tag == "a" and "button" in attrs.get("class", "").split()]
        self.assertEqual(len(buttons), 2)
        for attrs in buttons:
            self.assertEqual(attrs["href"], "#pending-publication")
            self.assertNotIn("data-package", attrs, "Release discovery must not replace pending links")
            self.assertIn("publication", attrs.get("aria-label", "").casefold())
        sections = [attrs.get("aria-labelledby") for tag, attrs in self.page.elements if tag == "section"]
        self.assertEqual(sections[-1], "pending-publication")
        notice = self.html.split('id="pending-publication"', 1)[1].split("</section>", 1)[0]
        self.assertIn("RVTools Analyzer Desktop", notice)
        self.assertIn("published Claude plugin", notice)
        self.assertNotIn("Plugin_9771f71b40a08191bb901469a275d3ba", self.html)

    def test_links_have_safe_schemes_and_internal_targets_exist(self):
        for tag, attrs in self.page.elements:
            if tag != "a":
                continue
            href = attrs["href"]
            if href.startswith("#"):
                self.assertIn(href[1:], self.page.ids)
            else:
                self.assertEqual(urlsplit(href).scheme, "https")
                self.assertIn(urlsplit(href).netloc, {"github.com", "rvtools.help", "knowledge.broadcom.com"})
        links = {attrs.get("href") for tag, attrs in self.page.elements if tag == "a"}
        anonymizer_links = [attrs["href"] for tag, attrs in self.page.elements
                            if tag == "a" and urlsplit(attrs["href"]).netloc == "rvtools.help"]
        self.assertEqual(anonymizer_links, ["https://rvtools.help/mask/"] * 2)
        self.assertIn(REPOSITORY + "#data-handling-and-privacy", links)
        self.assertIn(REPOSITORY + "#sample-reports", links)

    def test_site_has_no_workbook_inputs_tracking_or_remote_assets(self):
        for tag, attrs in self.page.elements:
            self.assertNotIn(tag, {"input", "form", "iframe", "object", "embed"})
            if tag == "script":
                self.assertNotIn("src", attrs)
            if tag == "link":
                self.assertNotEqual(attrs.get("rel"), "stylesheet")
        self.assertNotIn("localStorage", self.html)
        self.assertNotIn("sendBeacon", self.html)
        self.assertNotIn("innerHTML", self.html)
        self.assertEqual({path.name for path in (ROOT / "web").iterdir()},
                         {"index.html", "favicon.png", "favicon.svg"})

    def test_favicon_is_a_local_png_shared_with_plugin_packages(self):
        icons = [attrs for tag, attrs in self.page.elements if tag == "link" and attrs.get("rel") == "icon"]
        self.assertEqual(len(icons), 1)
        self.assertEqual(icons[0].get("href"), "./favicon.png")
        self.assertEqual(icons[0].get("type"), "image/png")
        self.assertTrue((ROOT / "web/favicon.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        csp = next(attrs["content"] for tag, attrs in self.page.elements
                   if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy")
        image_sources = next(item.strip() for item in csp.split(";") if item.strip().startswith("img-src"))
        self.assertIn("'self'", image_sources)
        self.assertNotIn("https:", image_sources)

    def test_workflow_deploys_only_web_independently_of_plugin_releases(self):
        path = ROOT / ".github/workflows/deploy-website.yml"
        self.assertTrue(path.is_file())
        workflow = path.read_text(encoding="utf-8")
        for required in (
            "workflow_dispatch:", "branches: [main]", '"web/**"',
            "python -m unittest discover -s tests -p test_website.py",
            "actions/configure-pages@", "actions/upload-pages-artifact@",
            "path: web", "actions/deploy-pages@", "pages: write", "id-token: write",
            "name: github-pages",
        ):
            self.assertIn(required, workflow)
        self.assertNotIn("workflow_run:", workflow)
        self.assertNotIn("tags:", workflow)
        self.assertIsNone(re.search(r"path:\s*['\"]?\.(?:/)?['\"]?\s*$", workflow, re.MULTILINE))


if __name__ == "__main__":
    unittest.main()

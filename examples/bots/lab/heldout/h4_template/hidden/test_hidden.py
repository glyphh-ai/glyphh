import unittest

from tmpl import render


class User:
    def __init__(self, name):
        self.name = name


class T(unittest.TestCase):
    def test_values_filters(self):
        self.assertEqual(render("Hi {{ user.name | upper }}!", {"user": {"name": "ann"}}), "Hi ANN!")
        self.assertEqual(render("{{ u.name|title }}", {"u": User("bo lee")}), "Bo Lee")
        self.assertEqual(render('{{ x | default:"none" }}', {}), "none")
        self.assertEqual(render('{{ tags | join:", " }}', {"tags": ["a", "b"]}), "a, b")
        self.assertEqual(render("[{{ missing }}]", {}), "[]")

    def test_escape(self):
        self.assertEqual(render("{{ s }}", {"s": "<b>&\"'"}), "&lt;b&gt;&amp;&quot;&#x27;")
        self.assertEqual(render("{{ s | safe }}", {"s": "<b>"}), "<b>")

    def test_if(self):
        t = "{% if a %}A{% if b %}B{% else %}b{% endif %}{% else %}none{% endif %}"
        self.assertEqual(render(t, {"a": 1, "b": 0}), "Ab")
        self.assertEqual(render(t, {"a": [], "b": 1}), "none")

    def test_for(self):
        t = "{% for x in xs %}{{ loop.index }}:{{ x }}{% if loop.last %}.{% else %},{% endif %}{% endfor %}"
        self.assertEqual(render(t, {"xs": ["a", "b", "c"]}), "1:a,2:b,3:c.")
        t2 = "{% for r in rows %}[{% for c in r %}{{ c }}{% endfor %}]{% endfor %}"
        self.assertEqual(render(t2, {"rows": [[1, 2], [3]]}), "[12][3]")

    def test_errors(self):
        for bad in ["{{ x | nope }}", "{% if a %}x", "{% endif %}", "{% for x in xs %}"]:
            with self.assertRaises(ValueError, msg=bad):
                render(bad, {"x": 1, "a": 1, "xs": []})

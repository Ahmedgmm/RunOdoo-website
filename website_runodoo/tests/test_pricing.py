from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPricing(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env['product.template']
        Product.search([('oh_plan', '!=', False)]).write({'sale_ok': False})
        cls.month = Product.create({'name': 'Business', 'type': 'service', 'list_price': 750, 'oh_plan': 'business',
                                    'oh_period': 'month', 'oh_workers': 2, 'oh_storage_gb': 25,
                                    'oh_highlight': True, 'oh_features': 'Priority support'})
        cls.year = Product.create({'name': 'Business yearly', 'type': 'service', 'list_price': 7500,
                                   'oh_plan': 'business', 'oh_period': 'year', 'oh_workers': 2, 'oh_storage_gb': 25})
        Product.create({'name': 'Hidden', 'type': 'service', 'list_price': 1, 'oh_plan': 'hidden', 'sale_ok': False})

    def test_cards_group_month_and_year(self):
        cards = self.env.ref('base.default_website')._runodoo_pricing()
        self.assertEqual([c['plan'] for c in cards], ['business'])
        self.assertEqual((cards[0]['month'], cards[0]['year']), (self.month, self.year))
        self.assertTrue(cards[0]['highlight'])

    def test_pricing_page_and_homepage(self):
        for path in ('/pricing', '/'):
            r = self.url_open(path)
            self.assertEqual(r.status_code, 200, path)
            for text in ('Business', '2 workers', '25 GB storage', 'Priority support', 'Most popular', 'Free trial'):
                self.assertIn(text, r.text, (path, text))
            self.assertNotIn('Hidden', r.text, path)
            self.assertNotIn('RAM', r.text, path)
        self.assertIn('/web/signup?redirect=%2Fmy%2Fplatform', self.url_open('/pricing').text)

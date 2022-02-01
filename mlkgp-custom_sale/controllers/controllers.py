# -*- coding: utf-8 -*-
# from odoo import http


# class Mlkgp-customSale(http.Controller):
#     @http.route('/mlkgp-custom_sale/mlkgp-custom_sale/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/mlkgp-custom_sale/mlkgp-custom_sale/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('mlkgp-custom_sale.listing', {
#             'root': '/mlkgp-custom_sale/mlkgp-custom_sale',
#             'objects': http.request.env['mlkgp-custom_sale.mlkgp-custom_sale'].search([]),
#         })

#     @http.route('/mlkgp-custom_sale/mlkgp-custom_sale/objects/<model("mlkgp-custom_sale.mlkgp-custom_sale"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('mlkgp-custom_sale.object', {
#             'object': obj
#         })

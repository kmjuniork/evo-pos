import functools
import logging
from odoo import http
from odoo.http import request
from odoo.addons.restful.common import valid_response, invalid_response, extract_arguments, extract_value
from datetime import timedelta, datetime, date
from dateutil.relativedelta import relativedelta
import dateutil.relativedelta

_logger = logging.getLogger(__name__)


def validate_token(func):
    @functools.wraps(func)
    def wrap(self, *args, **kwargs):
        access_token = request.httprequest.headers.get('access_token')
        if not access_token:
            return invalid_response('access_token_not_found', 'missing access token in request header', 401)

        request.session.authenticate(kwargs['db'], kwargs['login'], kwargs['password'])

        access_token_data = request.env['api.access_token'].sudo().search(
            [('token', '=', access_token)], order='id DESC', limit=1)

        if access_token_data.find_one_or_create_token(user_id=access_token_data.user_id.id) != access_token:
            return invalid_response('access_token', 'token seems to have expired or invalid', 401)

        request.session.uid = access_token_data.user_id.id
        request.uid = access_token_data.user_id.id
        return func(self, *args, **kwargs)

    return wrap

class ProductAPIController(http.Controller):

    # create product variant
    @validate_token
    @http.route("/api/create/product/variant", type='http', auth="none", methods=['POST'], csrf=False)
    def product_variant(self, **kwargs):
        product_tmpl_id = int(kwargs.get('product_tmpl_id'))
        attribute_id = int(kwargs.get('attribute_id'))
        attribute_value_id = int(kwargs.get('attribute_value_id'))
        price = int(kwargs.get('price')) if kwargs.get('price') else ''
        product_template_attribute_line_id = request.env['product.template.attribute.line'].sudo().search([('product_tmpl_id', '=', product_tmpl_id),('attribute_id', '=', attribute_id)]).id

        if product_template_attribute_line_id:
            request.env['product.template'].sudo().browse(product_tmpl_id).write({
                'attribute_line_ids': [(1, product_template_attribute_line_id, {
                    'value_ids': [(4, attribute_value_id)],
                })]
            })
        else:
            request.env['product.template'].sudo().browse(product_tmpl_id).write({
                'attribute_line_ids': [(0, False, {
                    'attribute_id': attribute_id,
                    'value_ids': [[6, False, [attribute_value_id]]],
                })]
            })

        if price:
            request.env['product.template.attribute.value'].sudo().search([('product_tmpl_id', '=', product_tmpl_id),('product_attribute_value_id', '=', attribute_value_id)]).write({
                    'price_extra': price,
            })
        data = request.env['product.product'].sudo().search_read([('product_tmpl_id', '=', product_tmpl_id)], limit=1,order='id desc')
        return valid_response(data)

    # sales by product api
    @validate_token
    @http.route("/api/update/product/variant/<id>", type='http', auth="none", methods=['PUT'], csrf=False)
    def update_product_variant(self, id=None, **payload):
        try:
            _id = int(id)
        except Exception as e:
            return invalid_response('invalid object id', 'invalid literal %s for id with base ' % id)
        domain, fields, offset, limit, order, context = extract_arguments(
            payload)
        if not context:
            context = request.env.context.copy()
        payload = extract_value(payload)
        if payload.get('price_extra'):
            request.env['product.template.attribute.value'].search(domain).sudo().write({
                'price_extra': payload.get('price_extra')
            })
        if payload.get('product_attribute_value_id'):
            attribute_value_id = request.env['product.template.attribute.value'].search(domain)
            old_product_attribute_value_id = attribute_value_id.product_attribute_value_id.id
            attribute_value_id.sudo().write({
                'product_attribute_value_id': payload.get('product_attribute_value_id')
            })
            product_variant_ids = attribute_value_id.product_tmpl_id.product_variant_ids.ids
            product_variant_ids = str(tuple(product_variant_ids)) if len(product_variant_ids) > 1 else "(" + str(product_variant_ids[0]) + ")"

            new_product_attribute_value_id = payload.get('product_attribute_value_id')
            attribute_line_id = attribute_value_id.product_tmpl_id.attribute_line_ids.id


            product_product_query = ("""update product_attribute_value_product_product_rel set product_attribute_value_id = %d
                                                               where product_product_id in %s and product_attribute_value_id= %d"""% (
            new_product_attribute_value_id, product_variant_ids, old_product_attribute_value_id))



            request.cr.execute(product_product_query)

            product_template_query = ("""update product_attribute_value_product_template_attribute_line_rel set product_attribute_value_id = %d
                                                               where product_template_attribute_line_id = %d and product_attribute_value_id= %d"""% (
            new_product_attribute_value_id, attribute_line_id, old_product_attribute_value_id))
            
            request.cr.execute(product_template_query)
        product = request.env['product.product'].sudo().browse(_id).write(payload)
        return valid_response('update product variant record with id %s successfully!' % (_id))


    # update product image path
    @validate_token
    @http.route("/api/update/product/image", type='http', auth="none", methods=['POST'], csrf=False)
    def product_image(self, **kwargs):

        products = request.env['product.product'].sudo().search([])
        for product in products:
            image_path = product.image_path
            if image_path:
                base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
                path = image_path.split('/web')
                new_image_path = image_path.replace(path[0], base_url)
                res = request.env['product.product'].sudo().browse(product.id)
                res.write({'image_path': new_image_path})

        data = {'message': 'Successfully updated image.'}
        return valid_response(data)

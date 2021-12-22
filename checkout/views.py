from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib import messages
from django.conf import settings

import stripe
from shopping_bag.contexts import shopping_bag_contents
from products.models import Product
from .forms import OrderForm
from .models import Order, OrderLineItem


def checkout(request):
    stripe_public_key = settings.STRIPE_PUBLIC_KEY
    stripe_secret_key = settings.STRIPE_SECRET_KEY

    if request.method == 'POST':
        print("Request Method = POST!!")
        shopping_bag_session = request.session.get('shopping_bag_session', {})

        form_data = {
            'full_name': request.POST['full_name'],
            'email': request.POST['email'],
            'phone_number': request.POST['phone_number'],
            'country': request.POST['country'],
            'postcode': request.POST['postcode'],
            'town_or_city': request.POST['town_or_city'],
            'street_address1': request.POST['street_address1'],
            'street_address2': request.POST['street_address2'],
            'county': request.POST['county'],
        }
        order_form = OrderForm(form_data)
        print("Checking if order form is valid.....")
        if order_form.is_valid():
            print("Order form is validated!! :-)")
            order = order_form.save()
            for item_id, item_data in shopping_bag_session.items():
                try:
                    product = Product.objects.get(id=item_id)
                    if isinstance(item_data, int):
                        order_line_item = OrderLineItem(
                            order=order,
                            product=product,
                            quantity=item_data,
                        )
                        order_line_item.save()
                        print("order_line_item = ", order_line_item)
                    else:
                        for size, quantity in item_data['items_by_size'].items():
                            order_line_item = OrderLineItem(
                                order=order,
                                product=product,
                                quantity=quantity,
                                product_size=size,
                            )
                            order_line_item.save()
                            print("order_line_item = ", order_line_item)
                except Product.DoesNotExist:
                    messages.error(request, (
                        "One of the products in your bag wasn't found in our database. "
                        "Please call us for assistance!")
                    )
                    order.delete()
                    return redirect(reverse('shopping_bag'))
            print("Order Line Items added - attempting to render 'Checkout Success'")
            request.session['save_info'] = 'save-info' in request.POST
            return redirect(reverse('checkout_success', args=[order.order_number]))
        else:
            print("Order for not validated - it is invalid!! :-(")
            messages.error(request, 'There was an error with your form. \
                Please double check your information.')

    else:
        print("Request Method is 'GET' ???")
        shopping_bag_session = request.session.get('shopping_bag_session', {})
        if not shopping_bag_session:
            messages.error(request, "There's nothing in your \
                bag at the moment")
            return redirect(reverse('products'))

        current_shopping_bag = shopping_bag_contents(request)
        current_total = current_shopping_bag['total_including_delivery']
        # convert the value into pennies/cents below
        stripe_total = round(current_total * 100)
        stripe.api_key = stripe_secret_key
        intent = stripe.PaymentIntent.create(
            amount=stripe_total,
            currency=settings.STRIPE_CURRENCY
        )

        order_form = OrderForm()

    if not stripe_public_key:
        messages.warning(request, 'You need to set your Public Key.  \
            Did you forget to set it in your environment?')

    template = 'checkout/checkout.html'
    context = {
        'order_form': order_form,
        'stripe_public_key': stripe_public_key,
        'client_secret': intent.client_secret,
    }

    return render(request, template, context)


def checkout_success(request, order_number):
    """
    Handle successful checkouts
    """
    save_info = request.session.get('save_info')
    order = get_object_or_404(Order, order_number=order_number)
    messages.success(request, f'Order successfully processed! \
        Your order number is {order_number}. A confirmation \
        email will be sent to {order.email}.')

    if 'shopping_bag_session' in request.session:
        del request.session['shopping_bag_session']

    template = 'checkout/checkout_success.html'
    context = {
        'order': order,
    }

    return render(request, template, context)



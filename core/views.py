from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, View
from django.shortcuts import redirect
from django.utils import timezone
from .forms import CheckoutForm, CouponForm, RefundForm, PaymentForm
from .models import Item, OrderItem, Order, Address, Payment, Coupon, Refund, UserProfile
from paypal.standard.forms import PayPalPaymentsForm
from django.http import JsonResponse

import json
import random
import string

def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


def products(request):
    context = {
        'items': Item.objects.all()
    }
    return render(request, "products.html", context)


def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid

def paymentComplete(request):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, ordered=False)
    form = PaymentForm(request.POST)
    userprofile = UserProfile.objects.get(user=request.user)
    
    if form.is_valid():
        save = form.cleaned_data.get('save')
        use_default = form.cleaned_data.get('use_default')
        amount = int(float(order.get_total) * 100)
        try:
            payment = Payment()
            payment.user = request.user
            payment.amount = order.get_total
            payment.save()            

            # assign the payment to the order
            order_items = order.items.filter(user=request.user)
            order_items.update(ordered=True)
            for item in order_items:
                item.save()
                order.ordered = True 
                order.payment = payment
                order.ref_code = create_ref_code() 
                order.save()
            messages.success(request, "Seu pedido foi feito com sucesso!")
            return redirect("core:home")
        except Exception as e:
                # send an email to ourselves
                messages.warning(
                    request, "A serious error occurred. We have been notifed.")
                return redirect("core:home")
    messages.warning(request, "Dados recebido invalidos.")
    return redirect("/payment/Paypal/")

class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            order_items = order.items.filter(user=self.request.user)
            form = CheckoutForm()
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }

            shipping_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='S',
                default=True
            )
            if shipping_address_qs.exists():
                context.update(
                    {'default_shipping_address': shipping_address_qs[0]})
            return render(self.request, "checkout.html", context)

        except ObjectDoesNotExist:
            messages.info(self.request, "Você não tem um pedido ativo")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            order_items = order.items.filter(user=self.request.user)   
            if form.is_valid():
                use_default_shipping = form.cleaned_data.get(
                    'use_default_shipping')
                if use_default_shipping:
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='S',
                        default=True
                    )
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.info(
                            self.request, "Nenhum endereço de entrega padrão disponível")
                        return redirect('core:checkout')
                else:
                    shipping_address1 = form.cleaned_data.get(
                        'shipping_address')
                    shipping_address2 = form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country = form.cleaned_data.get(
                        'shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')

                    if is_valid_form([shipping_address1, shipping_country, shipping_zip]):
                        shipping_address = Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type='S'
                        )
                        shipping_address.save()

                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get(
                            'set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()

                    else:
                        messages.info(
                            self.request, "Por favor, preencha o endereço de entrega.")

                payment_option = form.cleaned_data.get('payment_option')

                if payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
                else:
                    messages.warning(
                        self.request, "Opção de pagamento invalida. ")
                    return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.warning(self.request, "Você não tem um pedido ativo")
            return redirect("core:order-summary")

class PaymentView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            order_items = order.items.filter(user=self.request.user)
            if order.shipping_address:
                context = {
                    'order': order,
                    'DISPLAY_COUPON_FORM': False,
                    'order_items':order_items
                }
                """
                userprofile = self.request.user.userprofile
                if userprofile.one_click_purchasing:
                    pass
                self.request.session['order_id'] = order.id       
                """
                return render(self.request, "payment.html", context)
            else:
                messages.warning(
                    self.request, "Você não adicionou um endereço de entrega")
                return redirect("core:checkout")
        except:
            messages.warning(
                    self.request, "Você não tem um pedido existente")
            return redirect("core:home")
"""
    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        form = PaymentForm(self.request.POST)
        userprofile = UserProfile.objects.get(user=self.request.user)
        print(self.request)
        if form.is_valid():
            
            save = form.cleaned_data.get('save')
            use_default = form.cleaned_data.get('use_default')
            amount = int(order.get_total() * 100)

            try:
                # create the payment
                payment = Payment()
                payment.user = self.request.user
                payment.amount = order.get_total()
                payment.save()               

                # assign the payment to the order

                order_items = order.items.filter(user=self.request.user)
                print('passei por aquiiiiiiiiiiiiiiii')
                order_items.update(ordered=True)
                for item in order_items:
                    item.save()

                order.ordered = True
                order.payment = payment
                order.ref_code = create_ref_code()
                order.save()

                messages.success(self.request, "Seu pedido foi feito com sucesso!")
                return redirect("/")

            except Exception as e:
                # send an email to ourselves
                messages.warning(
                    self.request, "A serious error occurred. We have been notifed.")
                return redirect("/")

        messages.warning(self.request, "Dados recebido invalidos.")
        return redirect("/payment/Paypal/")
"""

class HomeView(ListView):
    model = Item
    paginate_by = 10
    template_name = "home.html"


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            order_items = order.items.filter(user=self.request.user)
            print(order_items)
            context = {
                'object': order,
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "Seu carrinho está vazio.")
            return redirect("/")
    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        userprofile = UserProfile.objects.get(user=self.request.user)


class ItemDetailView(DetailView):
    model = Item
    template_name = "product.html"



@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "A quantidade de itens foi atualizada.")
            return redirect("core:order-summary")
        else:
            order.items.add(order_item)
            messages.info(request, "O produto foi adicionado ao seu carrinho.")
            return redirect("core:order-summary")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "O produto foi adicionado ao seu carrinho.")
        return redirect("core:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            order_item.delete()
            messages.info(request, "O produto foi removido ao seu carrinho.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "O produto não estava no seu carrinho.")
            return redirect("core:product", slug=slug)
    else:
        messages.info(request, "Seu carrinho está vazio.")
        return redirect("core:product", slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, "A quantidade de itens foi atualizada.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "O produto não está no seu carirnho.")
            return redirect("core:product", slug=slug)
    else:
        messages.info(request, "Seu carinho está vazio.")
        return redirect("core:product", slug=slug)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "Esse cupom não existe.")
        return redirect("core:checkout")


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(
                    user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Cupom adicionado com sucesso.")
                return redirect("core:checkout")
            except ObjectDoesNotExist:
                messages.info(self.request, "Seu carrinho está vazio.")
                return redirect("core:checkout")


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            # edit the order
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                # store the refund
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.info(self.request, "Seu pedido foi recebido.")
                return redirect("core:request-refund")

            except ObjectDoesNotExist:
                messages.info(self.request, "Essa compra não existe.")
                return redirect("core:request-refund")
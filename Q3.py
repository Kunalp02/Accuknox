# Question 3: By default do django signals run in the same database transaction as the caller?
# Please support your answer with a code snippet that conclusively proves your stance. 
# The code does not need to be elegant and production ready, we just need to understand your logic.

# 
# We have a Customer model and a Payment model.
# After saving a Payment instance, we update the Customer's balance using a post_save signal.
# If the transaction fails , both the payment and the balance update should be rolled back.


# expected output
# [View] Making Payment... (Thread ID: 140694028969728)
# [Signal Handler] Updating customer balance to 100.00 (Thread ID: 140694028969728)
# [View] Simulated failure after payment creation!
# [View] Customer balance after transaction: 0.00

# CONCLUSION
# lastly the balance does not get updataed when the transcation gets failed 
# this proves that django signals runs in the same database as the caller by default

from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
import threading

class Customer(models.Model):
    name = models.CharField(max_length=100)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

# signal to update the customer balance 
@receiver(post_save, sender=Payment)
def update_customer_balance(sender, instance, **kwargs):
    customer = instance.customer
    customer.balance += instance.amount
    print(f"[Signal Handler] Updating customer balance to {customer.balance} (Thread ID: {threading.get_ident()})")
    customer.save()


from django.shortcuts import render
from .models import Payment, Customer
from django.db import transaction
import threading

def make_payment(request):
    customer = Customer.objects.first()

    print(f"[View] Making Payment... (Thread ID: {threading.get_ident()})")

    try:
        # payment object creating enclosed in transaction
        with transaction.atomic():
            payment = Payment.objects.create(
                customer=customer,
                amount=100.00  # Simulate payment amount
            )
            
            # exception for any error
            raise Exception("[View] Simulated failure after payment creation!")
    
    except Exception as e:
        print(e)

    # Reloading the customer from the database to check if the balance was updated
    customer.refresh_from_db()
    print(f"[View] Customer balance after transaction: {customer.balance}")

    return render(request, 'payment_result.html')


# Topic: Django Signals

# Question 1: By default are django signals executed synchronously
# or asynchronously? Please support your answer with a code snippet
# that conclusively proves your stance. The code does not need to be 
# elegant and production ready, we just need to understand your logic.

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
import time

class Order(models.Model):
    product = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    customer_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

# send confirmation email
@receiver(post_save, sender=Order)
def send_confirmation_email(sender, instance, **kwargs):
    print("Sending confirmation email...")
    time.sleep(3)  # Simulate a delay in sending the email
    print(f"Email sent to {instance.customer_email}")

# updating inventory
@receiver(post_save, sender=Order)
def update_inventory(sender, instance, **kwargs):
    print("Updating inventory...")
    time.sleep(2)  # Simulate a delay in updating the inventory
    print(f"Inventory updated for product {instance.product}")

# logging the order
@receiver(post_save, sender=Order)
def log_order(sender, instance, **kwargs):
    print("Logging order...")
    time.sleep(1)  # Simulate a delay in logging
    print(f"Order for {instance.product} logged.")

# creating the order
from django.shortcuts import render
from .models import Order

def create_order(request):
    # Simulating order creation
    order = Order.objects.create(
        product="Laptop",
        quantity=1,
        customer_email="customer@example.com"
    )
    return render(request, 'order_success.html')



# When the create_order view is called the following sequence will get executed
# CONCLUDING    
# The signal will trigger the send_confirmation_email function first, which waits for 3 seconds.
# After the email is "sent," the signal will trigger the update_inventory function, which waits for 2 seconds.
# Finally, the signal will trigger the log_order function, which waits for 1 second.
# All of these tasks will block the response from being sent to the user. 
# The response to the user will only be sent after 6 seconds (3s + 2s + 1s) because all the signals are executed synchronously.
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
import threading

class Order(models.Model):
    product = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    customer_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

# Send confirmation email
@receiver(post_save, sender=Order)
def send_confirmation_email(sender, instance, **kwargs):
    print(f"[Signal Handler] Sending confirmation email... (Thread ID: {threading.get_ident()})")

# Updating inventory
@receiver(post_save, sender=Order)
def update_inventory(sender, instance, **kwargs):
    print(f"[Signal Handler] Updating inventory... (Thread ID: {threading.get_ident()})")

# Logging order
@receiver(post_save, sender=Order)
def log_order(sender, instance, **kwargs):
    print(f"[Signal Handler] Logging order... (Thread ID: {threading.get_ident()})")


from django.shortcuts import render
from .models import Order
import threading

def create_order(request):
    print(f"[View] Creating Order... (Thread ID: {threading.get_ident()})")

    # Simulating order creation
    order = Order.objects.create(
        product="Laptop",
        quantity=1,
        customer_email="customer@example.com"
    )

    return render(request, 'order_success.html')


# threading.get_ident() function returns the thread ID in which the code is currently running. 
# In this case, the thread ID for the view and all signal handlers is the same, 
# indicating that all the signal handlers are running in the same thread as the view that triggered the signal.
# this proves that Django signals run in the same thread as the caller by default
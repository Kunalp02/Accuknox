from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
import threading
from django.shortcuts import render
import threading

# Question 2: Do django signals run in the same thread as the caller? Please support your answer with a code snippet that conclusively proves your stance. The code does not need to be elegant and production ready, we just need to understand your logic.


# CONCLUSION
# threading.get_ident() function returns the thread ID in which the code is currently running. 
# In this case, the thread ID for the view and all signal handlers is the same, 
# indicating that all the signal handlers are running in the same thread as the view that triggered the signal.
# this proves that Django signals run in the same thread as the caller by default

class Order(models.Model):
    product = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    customer_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

@receiver(post_save, sender=Order)
def send_confirmation_email(sender, instance, **kwargs):
    print(f"[Signal Handler] Sending confirmation email... (Thread ID: {threading.get_ident()})")

@receiver(post_save, sender=Order)
def update_inventory(sender, instance, **kwargs):
    print(f"[Signal Handler] Updating inventory... (Thread ID: {threading.get_ident()})")

@receiver(post_save, sender=Order)
def log_order(sender, instance, **kwargs):
    print(f"[Signal Handler] Logging order... (Thread ID: {threading.get_ident()})")


def create_order(request):
    print(f"[View] Creating Order... (Thread ID: {threading.get_ident()})")

    # Simulating order creation
    order = Order.objects.create(
        product="Laptop",
        quantity=1,
        customer_email="customer@example.com"
    )

    return render(request, 'order_success.html')


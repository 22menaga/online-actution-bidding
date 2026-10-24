// Loads Razorpay Checkout.js on demand (only when a customer actually pays).
let loading = null;

export function loadRazorpay() {
  if (window.Razorpay) return Promise.resolve(window.Razorpay);
  loading ??= new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.async = true;
    s.onload = () => resolve(window.Razorpay);
    s.onerror = () => { loading = null; reject(new Error('Could not load Razorpay. Check your internet connection and try again.')); };
    document.body.appendChild(s);
  });
  return loading;
}

/** Opens the Razorpay modal for a server-created order. Resolves with Razorpay's signed response, rejects on dismiss/failure. */
export async function openRazorpay(co) {
  const Razorpay = await loadRazorpay();
  return new Promise((resolve, reject) => {
    const rzp = new Razorpay({
      key: co.key_id,
      order_id: co.order_id,
      amount: co.amount,
      currency: co.currency,
      name: co.name,
      description: co.description,
      prefill: co.prefill,
      theme: { color: '#e0aa48' },
      modal: { ondismiss: () => reject(Object.assign(new Error('Payment window closed.'), { dismissed: true })) },
      handler: resolve,
    });
    rzp.on('payment.failed', (r) => reject(new Error(r.error?.description || 'Payment failed. Please try again.')));
    rzp.open();
  });
}

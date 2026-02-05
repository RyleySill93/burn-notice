const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;

      const el = entry.target as HTMLElement;
      const target = parseInt(el.dataset.countTo ?? '0', 10);
      const prefix = el.dataset.prefix ?? '';
      const suffix = el.dataset.suffix ?? '';
      const duration = 1500;
      const start = performance.now();

      const step = (now: number) => {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        // Ease-out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(eased * target);
        el.textContent = `${prefix}${current.toLocaleString()}${suffix}`;

        if (progress < 1) {
          requestAnimationFrame(step);
        }
      };

      requestAnimationFrame(step);
      observer.unobserve(el);
    });
  },
  { threshold: 0.3 }
);

document.querySelectorAll<HTMLElement>('[data-count-to]').forEach((el) => {
  observer.observe(el);
});

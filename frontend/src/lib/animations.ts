import type { Variants, Transition } from 'framer-motion';

// ============================================================
// Reusable framer-motion transition configs
// ============================================================

export const springGentle: Transition = {
  type: 'spring',
  stiffness: 300,
  damping: 25,
};

export const springBouncy: Transition = {
  type: 'spring',
  stiffness: 400,
  damping: 20,
};

export const springStiff: Transition = {
  type: 'spring',
  stiffness: 500,
  damping: 35,
};

export const easeOutExpo: Transition = {
  duration: 0.5,
  ease: [0.16, 1, 0.3, 1],
};

export const easeInOutExpo: Transition = {
  duration: 0.4,
  ease: [0.16, 1, 0.3, 1],
};

// ============================================================
// Reusable framer-motion variants
// ============================================================

/** Fade in + slide up from 8px below */
export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: easeOutExpo },
};

/** Fade in + slight scale up */
export const fadeInScale: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1, transition: easeOutExpo },
};

/** Fade in + slide up from 16px below (for larger elements) */
export const fadeInUpLarge: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: easeOutExpo },
};

/** Stagger container — children animate in sequence */
export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.04,
      delayChildren: 0.05,
    },
  },
};

/** Stagger item — used with staggerContainer */
export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] } },
};

/** Standard hover/tap interaction for clickable cards */
export const glassHover: Variants = {
  rest: { scale: 1, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' },
  hover: {
    scale: 1.02,
    boxShadow: '0 4px 16px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.03)',
    transition: springGentle,
  },
  tap: { scale: 0.98, transition: springStiff },
};

/** Full-page cinematic enter animation */
export const cinematicEnter: Variants = {
  hidden: { opacity: 0, filter: 'blur(8px)', scale: 0.97 },
  visible: {
    opacity: 1,
    filter: 'blur(0px)',
    scale: 1,
    transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
  },
  exit: {
    opacity: 0,
    filter: 'blur(4px)',
    scale: 1.02,
    transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] },
  },
};

/** View transition between pages */
export const viewTransition: Variants = {
  hidden: { opacity: 0, filter: 'blur(4px)', scale: 0.98 },
  visible: {
    opacity: 1,
    filter: 'blur(0px)',
    scale: 1,
    transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] },
  },
  exit: {
    opacity: 0,
    filter: 'blur(2px)',
    scale: 1.02,
    transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] },
  },
};

/** Toast / notification slide + scale */
export const toastVariants: Variants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: springBouncy,
  },
  exit: {
    opacity: 0,
    y: -10,
    scale: 0.95,
    transition: { duration: 0.2 },
  },
};

/** Inline edit panel pop-in */
export const editPanelVariants: Variants = {
  hidden: { opacity: 0, scale: 0.97, y: -4 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: springGentle,
  },
  exit: {
    opacity: 0,
    scale: 0.97,
    transition: { duration: 0.15 },
  },
};

/** Overlay backdrop fade */
export const overlayVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.2 } },
  exit: { opacity: 0, transition: { duration: 0.15 } },
};

/** Slide-in from left (for mobile panels) */
export const slideInLeft: Variants = {
  hidden: { x: '-100%' },
  visible: { x: 0, transition: springGentle },
  exit: { x: '-100%', transition: { duration: 0.2 } },
};

/** Slide-in from right (for mobile panels) */
export const slideInRight: Variants = {
  hidden: { x: '100%' },
  visible: { x: 0, transition: springGentle },
  exit: { x: '100%', transition: { duration: 0.2 } },
};

import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress ResizeObserver loop error - this is a benign error that occurs 
// when ResizeObserver delivers notifications during a resize loop
// See: https://stackoverflow.com/questions/49384120/resizeobserver-loop-limit-exceeded
const isResizeObserverError = (message) => {
  return message && (
    message.includes('ResizeObserver loop completed with undelivered notifications') ||
    message.includes('ResizeObserver loop limit exceeded')
  );
};

// Suppress the error from window error events
window.addEventListener('error', (e) => {
  if (isResizeObserverError(e.message)) {
    e.stopImmediatePropagation();
    e.stopPropagation();
    e.preventDefault();
    return false;
  }
});

// Suppress from unhandled rejection events
window.addEventListener('unhandledrejection', (e) => {
  if (e.reason && isResizeObserverError(e.reason.message)) {
    e.stopImmediatePropagation();
    e.stopPropagation();
    e.preventDefault();
    return false;
  }
});

// Override console.error to suppress ResizeObserver errors in dev mode
const originalConsoleError = console.error;
console.error = (...args) => {
  if (args[0] && typeof args[0] === 'string' && isResizeObserverError(args[0])) {
    return;
  }
  originalConsoleError.apply(console, args);
};

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

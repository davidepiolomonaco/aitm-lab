'use strict';

const form = document.getElementById('login-form');
const username = document.getElementById('username');
const password = document.getElementById('password');
const error = document.getElementById('form-error');
const toggle = document.getElementById('toggle-password');
const dialog = document.getElementById('demo-dialog');


toggle.addEventListener('click', () => {
  const visible = password.type === 'text';
  password.type = visible ? 'password' : 'text';
  toggle.textContent = visible ? 'Show' : 'Hide';
  toggle.setAttribute('aria-pressed', String(!visible));
  toggle.setAttribute('aria-label', visible ? 'Show password' : 'Hide password');
});

form.addEventListener('submit', (event) => {
  event.preventDefault();
  error.textContent = '';
  const email = username.value.trim().toLowerCase();
  const pw = password.value;
  if (!email || !pw) {
    error.textContent = 'Please enter your corporate email and password!';
  }
});

function closeDialog() { dialog.close(); }

document.getElementById('dialog-close').addEventListener('click', closeDialog);
document.getElementById('dialog-return').addEventListener('click', closeDialog);
dialog.addEventListener('click', e => { if (e.target === dialog) closeDialog(); });

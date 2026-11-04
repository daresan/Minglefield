// This is GUI validation only. The Rust execution boundary must independently
// validate the destination password before any encrypted database is created.
export function validateDestinationPassword(password, confirmation) {
  const missing = [];
  if ([...password].length < 8) missing.push("at least 8 characters");
  if (!/\p{Lu}/u.test(password)) missing.push("an uppercase letter");
  if (!/[0-9]/.test(password)) missing.push("a digit");
  if (![...password].some((c) => !/[\p{L}\p{N}\s]/u.test(c))) missing.push("a special character");
  if (missing.length) return { valid: false, message: "New database password requires " + missing.join(", ") + "." };
  if (password !== confirmation) return { valid: false, message: "Database password confirmation does not match." };
  return { valid: true, message: "Database encryption password and confirmation are valid." };
}

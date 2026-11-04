import test from "node:test";
import assert from "node:assert/strict";
import { validateDestinationPassword } from "./database-password-policy.js";

test("new encrypted database requires a password for every installation path", () => {
  assert.equal(validateDestinationPassword("", "").valid, false);
  assert.equal(validateDestinationPassword("lowercase1!", "lowercase1!").valid, false);
  assert.equal(validateDestinationPassword("Uppercase!", "Uppercase!").valid, false);
  assert.equal(validateDestinationPassword("Uppercase1", "Uppercase1").valid, false);
  assert.equal(validateDestinationPassword("Short1!", "Short1!").valid, false);
  assert.equal(validateDestinationPassword("ValidPass1!", "DifferentPass1!").valid, false);
  assert.equal(validateDestinationPassword("ValidPass1!", "ValidPass1!").valid, true);
});

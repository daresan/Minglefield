import test from "node:test";
import assert from "node:assert/strict";
import { createAlphaUserReview, updateAlphaUserReview, alphaUserCorrections } from "./alpha-user-review.js";

const source = [{ userId: "alice", disabled: false }, { userId: "bob", disabled: true }];
test("actual user records remain independent of edits", () => {
  const original = createAlphaUserReview(source);
  const edited = updateAlphaUserReview(original, "alice", true);
  assert.equal(original[0].disabled, false);
  assert.equal(edited[0].disabled, true);
  assert.deepEqual(alphaUserCorrections(original, edited), [{ userId: "alice", disabled: true }]);
});
test("reverting edits produces no migration corrections", () => {
  const original = createAlphaUserReview(source);
  const edited = updateAlphaUserReview(updateAlphaUserReview(original, "alice", true), "alice", false);
  assert.deepEqual(alphaUserCorrections(original, edited), []);
});
test("identity changes, duplicates and invalid values fail closed", () => {
  assert.throws(() => createAlphaUserReview([...source, source[0]]));
  assert.throws(() => updateAlphaUserReview(source, "unknown", true));
  assert.throws(() => updateAlphaUserReview(source, "alice", "true"));
  assert.throws(() => alphaUserCorrections(source, [{ userId: "other", disabled: false }, source[1]]));
  assert.throws(() => alphaUserCorrections(source, source.slice(1)));
});

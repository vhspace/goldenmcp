import { describe, expect, test } from "bun:test";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { LANDING_SPONSOR_TRACKS } from "../src/lib/landing-content";

const publicRoot = join(import.meta.dir, "..", "public");

describe("sponsor logo assets (GH #124)", () => {
  test("logo SVG files exist under public/images/sponsors", () => {
    for (const track of LANDING_SPONSOR_TRACKS.tracks) {
      const filePath = join(publicRoot, track.logoSrc.replace(/^\//, ""));
      expect(existsSync(filePath)).toBe(true);
    }
  });
});

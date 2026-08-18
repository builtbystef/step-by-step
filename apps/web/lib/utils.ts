import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * The type scale is six named sizes rather than Tailwind's t-shirt scale, so
 * tailwind-merge is told they are font sizes. Without this it reads
 * `text-half` as a colour and lets a generated component's `text-sm` survive
 * beside it, and the later of the two in the stylesheet wins at random.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["micro", "small", "half", "body", "title", "page"] }],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

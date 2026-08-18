import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/*
 * tailwind-merge only knows Tailwind's own font sizes. Without the six of
 * ours taught to it, `text-half` reads as a colour and a generated `text-sm`
 * survives beside it, leaving stylesheet order to decide which one wins.
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

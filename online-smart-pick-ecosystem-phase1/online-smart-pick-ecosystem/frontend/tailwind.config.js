/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand palette
        brand: {
          // Deep Blue — primary
          blue: {
            DEFAULT: "#1E3A5F",
            50: "#E8EDF3",
            100: "#D1DBE7",
            200: "#A3B7CF",
            300: "#7593B7",
            400: "#476F9F",
            500: "#1E3A5F",
            600: "#182E4C",
            700: "#122339",
            800: "#0C1726",
            900: "#060C13",
          },
          // Green — success / accent
          green: {
            DEFAULT: "#10B981",
            50: "#E7F9F2",
            100: "#CFF3E5",
            200: "#9FE7CB",
            300: "#6FDBB1",
            400: "#3FCF97",
            500: "#10B981",
            600: "#0D9467",
            700: "#0A6F4D",
            800: "#064A34",
            900: "#03251A",
          },
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

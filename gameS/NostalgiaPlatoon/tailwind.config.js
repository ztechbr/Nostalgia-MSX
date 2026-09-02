/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html"],
  theme: {
    extend: {
      fontFamily: {
        pixel: ['"Press Start 2P"', "monospace"],
      },
      colors: {
        // MSX1 (TMS9918) 16-color palette
        msx: {
          black: "#000000",
          blue: "#3EB0FF",
          "dark-blue": "#0000AA",
          red: "#B7362F",
          cyan: "#5CE1E6",
          magenta: "#B766C6",
          green: "#3EAE3E",
          "dark-green": "#005500",
          "light-green": "#74D07D",
          yellow: "#D0DC71",
          "dark-yellow": "#C0B03E",
          gray: "#CCCCCC",
          white: "#FFFFFF",
        },
      },
      boxShadow: {
        pixel: "4px 4px 0 0 rgba(0,0,0,0.6)",
      },
    },
  },
  plugins: [],
};

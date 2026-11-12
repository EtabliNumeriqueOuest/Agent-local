const config = {
  // @tailwindcss/postcss (devDependencies de package.json) suffit : Tailwind v4 ajoute lui-même les préfixes navigateur, sans autoprefixer
  plugins: ["@tailwindcss/postcss"],
};

export default config;

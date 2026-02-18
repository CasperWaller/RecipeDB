import { useEffect, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

function toTitleCase(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function App() {
  const [recipes, setRecipes] = useState([]);
  const [selectedRecipeId, setSelectedRecipeId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [backendStatus, setBackendStatus] = useState("checking");

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [ingredientsText, setIngredientsText] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchScope, setSearchScope] = useState("all");
  const [saving, setSaving] = useState(false);
  const selectedRecipe = recipes.find((recipe) => recipe.id === selectedRecipeId) || null;

  async function loadRecipes(options = {}) {
    const query = options.query ?? searchQuery;
    const scope = options.scope ?? searchScope;
    setLoading(true);
    setError("");
    setBackendStatus("checking");
    try {
      const params = new URLSearchParams();
      if (query.trim()) {
        params.set("query", query.trim());
        params.set("scope", scope);
      }
      const url = `${API_BASE}/recipes/${params.toString() ? `?${params.toString()}` : ""}`;
      const response = await fetch(url);
      if (!response.ok) {
        setBackendStatus("disconnected");
        throw new Error(`Failed to load recipes (${response.status})`);
      }
      const data = await response.json();
      setBackendStatus("connected");
      setRecipes(Array.isArray(data) ? data : []);
      setSelectedRecipeId((previousId) => {
        if (!Array.isArray(data) || data.length === 0) {
          return null;
        }
        if (previousId && data.some((recipe) => recipe.id === previousId)) {
          return previousId;
        }
        return data[0].id;
      });
    } catch (err) {
      setBackendStatus("disconnected");
      setError(err instanceof Error ? err.message : "Failed to load recipes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      loadRecipes();
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchQuery, searchScope]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }

    setSaving(true);
    setError("");

    const ingredientNames = ingredientsText
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean);

    const tagNames = tagsText
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean);

    const payload = {
      title: title.trim(),
      description: description.trim() || null,
      ingredients: ingredientNames.map((name) => ({ name })),
      tags: tagNames.map((name) => ({ name })),
    };

    try {
      const response = await fetch(`${API_BASE}/recipes/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Failed to create recipe (${response.status})`);
      }

      setTitle("");
      setDescription("");
      setIngredientsText("");
      setTagsText("");
      await loadRecipes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create recipe");
    } finally {
      setSaving(false);
    }
  }

  function clearSearch() {
    setSearchQuery("");
    setSearchScope("all");
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8 flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">Recipe App</h1>
            <p className="mt-1 text-sm text-slate-600">Create and browse your recipes in one place.</p>
          </div>
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
          >
            Open API Docs
          </a>
        </header>

        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Total recipes</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900">{recipes.length}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Backend</p>
            <p
              className={`mt-1 text-base font-medium ${
                backendStatus === "connected"
                  ? "text-emerald-600"
                  : backendStatus === "checking"
                    ? "text-amber-600"
                    : "text-rose-600"
              }`}
            >
              {backendStatus === "connected"
                ? "Connected"
                : backendStatus === "checking"
                  ? "Checking..."
                  : "Disconnected"}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Status</p>
            <p className="mt-1 text-base font-medium text-slate-700">{loading ? "Loading data" : "Ready"}</p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-5">
          <section className="rounded-2xl border border-slate-200 bg-white p-6 lg:col-span-2">
            <h2 className="text-lg font-semibold text-slate-900">Add Recipe</h2>
            <p className="mt-1 text-sm text-slate-500">Fill out the form to create a new recipe.</p>

            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Title</span>
                <input
                  type="text"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="e.g. Spaghetti"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Description</span>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Short description"
                  rows={3}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Ingredients</span>
                <input
                  type="text"
                  value={ingredientsText}
                  onChange={(event) => setIngredientsText(event.target.value)}
                  placeholder="tomato, garlic, pasta"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Tags</span>
                <input
                  type="text"
                  value={tagsText}
                  onChange={(event) => setTagsText(event.target.value)}
                  placeholder="dinner, italian"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                />
              </label>

              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={saving}
                  className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving ? "Saving..." : "Create Recipe"}
                </button>
                <button
                  type="button"
                  onClick={loadRecipes}
                  disabled={loading}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Refresh
                </button>
              </div>
            </form>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 lg:col-span-3">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">Recipes</h2>
              {loading ? <span className="text-sm text-slate-500">Loading...</span> : null}
            </div>

            <div className="mb-4 flex flex-col gap-2 sm:flex-row">
              <input
                type="text"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search recipes..."
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
              />
              <select
                value={searchScope}
                onChange={(event) => setSearchScope(event.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-400"
              >
                <option value="all">All</option>
                <option value="name">Name</option>
                <option value="ingredients">Ingredients</option>
                <option value="tags">Tags</option>
              </select>
              <button
                type="button"
                onClick={clearSearch}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Clear
              </button>
            </div>

            {error ? (
              <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>
            ) : null}

            {!loading && recipes.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-slate-500">
                No recipes yet. Add your first recipe from the form.
              </div>
            ) : null}

            {recipes.length > 0 ? (
              <>
                {selectedRecipe ? (
                  <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <h3 className="text-base font-semibold text-slate-900">{selectedRecipe.title}</h3>
                    {selectedRecipe.description ? (
                      <p className="mt-1 text-sm text-slate-600">{selectedRecipe.description}</p>
                    ) : (
                      <p className="mt-1 text-sm text-slate-500">No description</p>
                    )}

                    <div className="mt-3 text-sm text-slate-700">
                      <strong>Ingredients:</strong>{" "}
                      {(selectedRecipe.ingredients || []).length > 0
                        ? selectedRecipe.ingredients.map((item) => toTitleCase(item.name)).join(", ")
                        : "-"}
                    </div>
                    <div className="mt-1 text-sm text-slate-700">
                      <strong>Tags:</strong>{" "}
                      {(selectedRecipe.tags || []).length > 0
                        ? selectedRecipe.tags.map((item) => `#${item.name}`).join(", ")
                        : "-"}
                    </div>
                    <div className="mt-1 text-sm text-slate-700">
                      <strong>Prep/Cook:</strong>{" "}
                      {selectedRecipe.prep_time ?? "-"} / {selectedRecipe.cook_time ?? "-"} min
                    </div>
                  </div>
                ) : null}

                <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Tap a recipe for details</p>
                <ul className="space-y-3">
                {recipes.map((recipe) => (
                  <li key={recipe.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedRecipeId(recipe.id)}
                      className={`w-full rounded-xl border p-4 text-left transition ${
                        selectedRecipeId === recipe.id
                          ? "border-slate-900 bg-slate-100"
                          : "border-slate-200 bg-white hover:bg-slate-50"
                      }`}
                    >
                      <h3 className="text-base font-semibold text-slate-900">{recipe.title}</h3>
                      <p className="mt-1 text-sm text-slate-600">
                        {(recipe.ingredients || []).length} ingredients · {(recipe.tags || []).length} tags
                      </p>
                    </button>
                  </li>
                ))}
                </ul>
              </>
            ) : null}
          </section>
        </div>
      </div>
    </main>
  );
}

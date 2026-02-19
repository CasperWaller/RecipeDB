import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function toTitleCase(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function parseList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function findDuplicates(values) {
  const counts = new Map();
  values.forEach((value) => {
    const normalized = value.toLowerCase();
    counts.set(normalized, (counts.get(normalized) || 0) + 1);
  });
  return [...counts.entries()].filter(([, count]) => count > 1).map(([value]) => value);
}

function validateRecipeForm({ title, prepTime, cookTime, ingredientsText, tagsText }) {
  const errors = {};
  const ingredientNames = parseList(ingredientsText);
  const tagNames = parseList(tagsText);

  if (!title.trim()) {
    errors.title = "Title is required";
  }

  if (prepTime.trim() && Number(prepTime) < 0) {
    errors.prepTime = "Prep time cannot be negative";
  }

  if (cookTime.trim() && Number(cookTime) < 0) {
    errors.cookTime = "Cook time cannot be negative";
  }

  const duplicateIngredients = findDuplicates(ingredientNames);
  if (duplicateIngredients.length > 0) {
    errors.ingredients = `Duplicate ingredients: ${duplicateIngredients.join(", ")}`;
  }

  const duplicateTags = findDuplicates(tagNames);
  if (duplicateTags.length > 0) {
    errors.tags = `Duplicate tags: ${duplicateTags.join(", ")}`;
  }

  return { errors, ingredientNames, tagNames };
}

function toPdfFileName(value) {
  const normalized = String(value || "recipe")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `${normalized || "recipe"}.pdf`;
}

async function getApiErrorMessage(response, fallback) {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string" && data.detail.trim()) {
      return data.detail;
    }
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      const first = data.detail[0];
      if (typeof first === "string") {
        return first;
      }
      if (typeof first?.msg === "string" && first.msg.trim()) {
        return first.msg;
      }
    }
    if (typeof data?.message === "string" && data.message.trim()) {
      return data.message;
    }
  } catch {
    // no-op
  }

  return `${fallback} (${response.status})`;
}

export default function App() {
  const SORT_STORAGE_KEY = "recipe_sort_by";
  const allowedSortModes = new Set(["newest", "prep", "title"]);
  const [recipes, setRecipes] = useState([]);
  const [selectedRecipeId, setSelectedRecipeId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [backendStatus, setBackendStatus] = useState("checking");

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [prepTime, setPrepTime] = useState("");
  const [cookTime, setCookTime] = useState("");
  const [ingredientsText, setIngredientsText] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editPrepTime, setEditPrepTime] = useState("");
  const [editCookTime, setEditCookTime] = useState("");
  const [editIngredientsText, setEditIngredientsText] = useState("");
  const [editTagsText, setEditTagsText] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchScope, setSearchScope] = useState("all");
  const [authMode, setAuthMode] = useState("login");
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authSaving, setAuthSaving] = useState(false);
  const [token, setToken] = useState(localStorage.getItem("auth_token") || "");
  const [currentUser, setCurrentUser] = useState(null);
  const [saving, setSaving] = useState(false);
  const [recipeDeleting, setRecipeDeleting] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [commentSaving, setCommentSaving] = useState(false);
  const [commentDeletingId, setCommentDeletingId] = useState(null);
  const [sortBy, setSortBy] = useState(() => {
    const saved = localStorage.getItem(SORT_STORAGE_KEY) || "newest";
    return allowedSortModes.has(saved) ? saved : "newest";
  });
  const [createValidationErrors, setCreateValidationErrors] = useState({});
  const [editValidationErrors, setEditValidationErrors] = useState({});
  const selectedRecipe = recipes.find((recipe) => recipe.id === selectedRecipeId) || null;
  const isAdmin = Boolean(currentUser?.is_admin);
  const canEditSelectedRecipe = Boolean(
    selectedRecipe && currentUser && (isAdmin || selectedRecipe.created_by_username === currentUser.username)
  );

  const sortedRecipes = useMemo(() => {
    const items = [...recipes];
    if (sortBy === "title") {
      return items.sort((a, b) => (a.title || "").localeCompare(b.title || ""));
    }
    if (sortBy === "prep") {
      return items.sort((a, b) => {
        const aValue = a.prep_time == null ? Number.POSITIVE_INFINITY : a.prep_time;
        const bValue = b.prep_time == null ? Number.POSITIVE_INFINITY : b.prep_time;
        return aValue - bValue;
      });
    }
    return items.sort((a, b) => b.id - a.id);
  }, [recipes, sortBy]);

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
        throw new Error(await getApiErrorMessage(response, "Failed to load recipes"));
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

  useEffect(() => {
    async function loadCurrentUser() {
      if (!token) {
        setCurrentUser(null);
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          localStorage.removeItem("auth_token");
          setToken("");
          setCurrentUser(null);
          return;
        }
        const user = await response.json();
        setCurrentUser(user);
      } catch {
        setCurrentUser(null);
      }
    }

    loadCurrentUser();
  }, [token]);

  useEffect(() => {
    setEditMode(false);
  }, [selectedRecipeId]);

  useEffect(() => {
    localStorage.setItem(SORT_STORAGE_KEY, sortBy);
  }, [sortBy, SORT_STORAGE_KEY]);

  function getAuthHeaders() {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setCreateValidationErrors({});

    if (!token) {
      setError("Please log in to create recipes");
      return;
    }

    const { errors, ingredientNames, tagNames } = validateRecipeForm({
      title,
      prepTime,
      cookTime,
      ingredientsText,
      tagsText,
    });

    if (Object.keys(errors).length > 0) {
      setCreateValidationErrors(errors);
      return;
    }

    setSaving(true);

    const payload = {
      title: title.trim(),
      description: description.trim() || null,
      prep_time: prepTime.trim() ? Number(prepTime) : null,
      cook_time: cookTime.trim() ? Number(cookTime) : null,
      ingredients: ingredientNames.map((name) => ({ name })),
      tags: tagNames.map((name) => ({ name })),
    };

    try {
      const response = await fetch(`${API_BASE}/recipes/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, "Failed to create recipe"));
      }

      setTitle("");
      setDescription("");
      setPrepTime("");
      setCookTime("");
      setIngredientsText("");
      setTagsText("");
      setCreateValidationErrors({});
      await loadRecipes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create recipe");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddComment(event) {
    event.preventDefault();
    if (!selectedRecipeId || !commentText.trim()) {
      return;
    }

    setCommentSaving(true);
    setError("");

    if (!token) {
      setError("Please log in to add comments");
      setCommentSaving(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/recipes/${selectedRecipeId}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ content: commentText.trim() }),
      });

      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, "Failed to add comment"));
      }

      setCommentText("");
      await loadRecipes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add comment");
    } finally {
      setCommentSaving(false);
    }
  }

  async function handleDeleteComment(commentId) {
    if (!selectedRecipeId) {
      return;
    }

    setCommentDeletingId(commentId);
    setError("");

    if (!token) {
      setError("Please log in to remove comments");
      setCommentDeletingId(null);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/recipes/${selectedRecipeId}/comments/${commentId}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, "Failed to delete comment"));
      }

      await loadRecipes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete comment");
    } finally {
      setCommentDeletingId(null);
    }
  }

  async function handleDeleteRecipe() {
    if (!selectedRecipeId) {
      return;
    }

    if (!token) {
      setError("Please log in to remove recipes");
      return;
    }

    if (!isAdmin) {
      setError("Only admin can remove recipes");
      return;
    }

    setRecipeDeleting(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE}/recipes/${selectedRecipeId}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, "Failed to delete recipe"));
      }

      await loadRecipes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete recipe");
    } finally {
      setRecipeDeleting(false);
    }
  }

  function startEditRecipe() {
    if (!selectedRecipe) {
      return;
    }

    setEditTitle(selectedRecipe.title || "");
    setEditDescription(selectedRecipe.description || "");
    setEditPrepTime(selectedRecipe.prep_time != null ? String(selectedRecipe.prep_time) : "");
    setEditCookTime(selectedRecipe.cook_time != null ? String(selectedRecipe.cook_time) : "");
    setEditIngredientsText((selectedRecipe.ingredients || []).map((item) => item.name).join(", "));
    setEditTagsText((selectedRecipe.tags || []).map((item) => item.name).join(", "));
    setEditValidationErrors({});
    setEditMode(true);
  }

  function cancelEditRecipe() {
    setEditValidationErrors({});
    setEditMode(false);
  }

  async function handleUpdateRecipe(event) {
    event.preventDefault();
    if (!selectedRecipeId) {
      return;
    }

    if (!token) {
      setError("Please log in to edit recipes");
      return;
    }

    if (!canEditSelectedRecipe) {
      setError("Only the recipe owner can edit this recipe");
      return;
    }
    setEditValidationErrors({});
    const { errors, ingredientNames, tagNames } = validateRecipeForm({
      title: editTitle,
      prepTime: editPrepTime,
      cookTime: editCookTime,
      ingredientsText: editIngredientsText,
      tagsText: editTagsText,
    });

    if (Object.keys(errors).length > 0) {
      setEditValidationErrors(errors);
      return;
    }

    const payload = {
      title: editTitle.trim(),
      description: editDescription.trim() || null,
      prep_time: editPrepTime.trim() ? Number(editPrepTime) : null,
      cook_time: editCookTime.trim() ? Number(editCookTime) : null,
      ingredients: ingredientNames.map((name) => ({ name })),
      tags: tagNames.map((name) => ({ name })),
    };

    setEditSaving(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/recipes/${selectedRecipeId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, "Failed to update recipe"));
      }

      await loadRecipes();
      setEditMode(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update recipe");
    } finally {
      setEditSaving(false);
    }
  }

  function clearSearch() {
    setSearchQuery("");
    setSearchScope("all");
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();
    if (!authUsername.trim() || !authPassword) {
      setError("Username and password are required");
      return;
    }

    setAuthSaving(true);
    setError("");
    try {
      if (authMode === "register") {
        const registerResponse = await fetch(`${API_BASE}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: authUsername.trim(), password: authPassword }),
        });
        if (!registerResponse.ok) {
          throw new Error(await getApiErrorMessage(registerResponse, "Registration failed"));
        }
      }

      const loginResponse = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: authUsername.trim(), password: authPassword }),
      });

      if (!loginResponse.ok) {
        throw new Error(await getApiErrorMessage(loginResponse, "Login failed"));
      }

      const data = await loginResponse.json();
      localStorage.setItem("auth_token", data.token);
      setToken(data.token);
      setCurrentUser(data.user);
      setAuthPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setAuthSaving(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("auth_token");
    setToken("");
    setCurrentUser(null);
  }

  async function handleExportRecipePdf() {
    if (!selectedRecipe) {
      setError("Select a recipe to export");
      return;
    }

    const { jsPDF } = await import("jspdf");

    const doc = new jsPDF({ unit: "pt", format: "a4" });
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 44;
    const maxWidth = pageWidth - margin * 2;
    const lineHeight = 16;
    let cursorY = margin;

    const ensureSpace = (neededHeight = lineHeight) => {
      if (cursorY + neededHeight <= pageHeight - margin) {
        return;
      }
      doc.addPage();
      cursorY = margin;
    };

    const writeHeading = (text) => {
      ensureSpace(28);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(22);
      doc.text(text, margin, cursorY);
      cursorY += 28;
    };

    const writeLabel = (text) => {
      ensureSpace(18);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(12);
      doc.text(text, margin, cursorY);
      cursorY += 18;
    };

    const writeBody = (text) => {
      const lines = doc.splitTextToSize(String(text || "-"), maxWidth);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(11);
      lines.forEach((line) => {
        ensureSpace(lineHeight);
        doc.text(line, margin, cursorY);
        cursorY += lineHeight;
      });
      cursorY += 6;
    };

    writeHeading(selectedRecipe.title || "Recipe");

    writeLabel("Created by");
    writeBody(selectedRecipe.created_by_username || "Unknown user");

    writeLabel("Description");
    writeBody(selectedRecipe.description || "No description");

    writeLabel("Prep / Cook");
    writeBody(`${selectedRecipe.prep_time ?? "-"} / ${selectedRecipe.cook_time ?? "-"} min`);

    writeLabel("Ingredients");
    const ingredientText = (selectedRecipe.ingredients || []).length
      ? selectedRecipe.ingredients.map((item) => `• ${toTitleCase(item.name)}`).join("\n")
      : "-";
    writeBody(ingredientText);

    writeLabel("Tags");
    const tagsTextValue = (selectedRecipe.tags || []).length
      ? selectedRecipe.tags.map((item) => `#${item.name}`).join(", ")
      : "-";
    writeBody(tagsTextValue);

    writeLabel("Comments");
    const comments = selectedRecipe.comments || [];
    if (comments.length === 0) {
      writeBody("No comments");
    } else {
      comments.forEach((comment, index) => {
        const author = comment.created_by_username || "Unknown user";
        const timestamp = comment.created_at ? new Date(comment.created_at).toLocaleString() : "";
        const header = timestamp ? `${index + 1}. ${author} (${timestamp})` : `${index + 1}. ${author}`;
        writeBody(`${header}\n${comment.content}`);
      });
    }

    doc.save(toPdfFileName(selectedRecipe.title));
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

        <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-4">
          {currentUser ? (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-700">
                Logged in as <strong>{currentUser.username}</strong>{" "}
                <span className={isAdmin ? "text-emerald-700" : "text-slate-500"}>
                  ({isAdmin ? "Admin" : "User"})
                </span>
              </p>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Logout
              </button>
            </div>
          ) : (
            <form onSubmit={handleAuthSubmit} className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <input
                type="text"
                value={authUsername}
                onChange={(event) => setAuthUsername(event.target.value)}
                placeholder="Username"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-400 sm:w-48"
              />
              <input
                type="password"
                value={authPassword}
                onChange={(event) => setAuthPassword(event.target.value)}
                placeholder="Password"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-400 sm:w-48"
              />
              <button
                type="submit"
                disabled={authSaving}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {authSaving ? "Please wait..." : authMode === "login" ? "Login" : "Register"}
              </button>
              <button
                type="button"
                onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                {authMode === "login" ? "Switch to Register" : "Switch to Login"}
              </button>
            </form>
          )}
        </section>

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
                  onChange={(event) => {
                    setTitle(event.target.value);
                    setCreateValidationErrors((previous) => ({ ...previous, title: "" }));
                  }}
                  placeholder="e.g. Spaghetti"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                />
                {createValidationErrors.title ? (
                  <p className="mt-1 text-xs text-rose-600">{createValidationErrors.title}</p>
                ) : null}
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
                  onChange={(event) => {
                    setIngredientsText(event.target.value);
                    setCreateValidationErrors((previous) => ({ ...previous, ingredients: "" }));
                  }}
                  placeholder="tomato, garlic, pasta"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                />
                {createValidationErrors.ingredients ? (
                  <p className="mt-1 text-xs text-rose-600">{createValidationErrors.ingredients}</p>
                ) : null}
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-slate-700">Prep Time (min)</span>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={prepTime}
                    onChange={(event) => {
                      setPrepTime(event.target.value);
                      setCreateValidationErrors((previous) => ({ ...previous, prepTime: "" }));
                    }}
                    placeholder="e.g. 15"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                  />
                  {createValidationErrors.prepTime ? (
                    <p className="mt-1 text-xs text-rose-600">{createValidationErrors.prepTime}</p>
                  ) : null}
                </label>

                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-slate-700">Cook Time (min)</span>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={cookTime}
                    onChange={(event) => {
                      setCookTime(event.target.value);
                      setCreateValidationErrors((previous) => ({ ...previous, cookTime: "" }));
                    }}
                    placeholder="e.g. 30"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                  />
                  {createValidationErrors.cookTime ? (
                    <p className="mt-1 text-xs text-rose-600">{createValidationErrors.cookTime}</p>
                  ) : null}
                </label>
              </div>

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Tags</span>
                <input
                  type="text"
                  value={tagsText}
                  onChange={(event) => {
                    setTagsText(event.target.value);
                    setCreateValidationErrors((previous) => ({ ...previous, tags: "" }));
                  }}
                  placeholder="dinner, italian"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                />
                {createValidationErrors.tags ? (
                  <p className="mt-1 text-xs text-rose-600">{createValidationErrors.tags}</p>
                ) : null}
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
              <select
                value={sortBy}
                onChange={(event) => setSortBy(event.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-400"
              >
                <option value="newest">Newest</option>
                <option value="prep">Prep Time</option>
                <option value="title">A-Z</option>
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

            {loading ? (
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-slate-500">
                Loading recipes...
              </div>
            ) : null}

            {!loading && recipes.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-slate-500">
                {searchQuery.trim()
                  ? "No recipes match your search. Try another keyword or scope."
                  : "No recipes yet. Add your first recipe from the form."}
              </div>
            ) : null}

            {recipes.length > 0 ? (
              <>
                {selectedRecipe ? (
                  <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-base font-semibold text-slate-900">{selectedRecipe.title}</h3>
                        <p className="mt-1 text-xs text-slate-500">
                          Created by {selectedRecipe.created_by_username || "Unknown user"}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={handleExportRecipePdf}
                          className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                        >
                          Export PDF
                        </button>
                        {canEditSelectedRecipe ? (
                          <button
                            type="button"
                            onClick={startEditRecipe}
                            disabled={editMode}
                            className="rounded-md border border-slate-300 px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            Edit Recipe
                          </button>
                        ) : null}
                        {isAdmin ? (
                          <button
                            type="button"
                            onClick={handleDeleteRecipe}
                            disabled={recipeDeleting}
                            className="rounded-md border border-rose-200 px-2.5 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {recipeDeleting ? "Removing..." : "Remove Recipe"}
                          </button>
                        ) : null}
                      </div>
                    </div>
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

                    {editMode ? (
                      <form onSubmit={handleUpdateRecipe} className="mt-4 space-y-3 rounded-lg border border-slate-200 bg-white p-3">
                        <p className="text-sm font-medium text-slate-900">Edit Recipe</p>
                        <label className="block">
                          <span className="mb-1 block text-xs font-medium text-slate-700">Title</span>
                          <input
                            type="text"
                            value={editTitle}
                            onChange={(event) => {
                              setEditTitle(event.target.value);
                              setEditValidationErrors((previous) => ({ ...previous, title: "" }));
                            }}
                            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 focus:border-slate-400"
                          />
                          {editValidationErrors.title ? (
                            <p className="mt-1 text-xs text-rose-600">{editValidationErrors.title}</p>
                          ) : null}
                        </label>
                        <label className="block">
                          <span className="mb-1 block text-xs font-medium text-slate-700">Description</span>
                          <textarea
                            value={editDescription}
                            onChange={(event) => setEditDescription(event.target.value)}
                            rows={3}
                            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 focus:border-slate-400"
                          />
                        </label>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <label className="block">
                            <span className="mb-1 block text-xs font-medium text-slate-700">Prep Time (min)</span>
                            <input
                              type="number"
                              min="0"
                              step="1"
                              value={editPrepTime}
                              onChange={(event) => {
                                setEditPrepTime(event.target.value);
                                setEditValidationErrors((previous) => ({ ...previous, prepTime: "" }));
                              }}
                              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 focus:border-slate-400"
                            />
                            {editValidationErrors.prepTime ? (
                              <p className="mt-1 text-xs text-rose-600">{editValidationErrors.prepTime}</p>
                            ) : null}
                          </label>
                          <label className="block">
                            <span className="mb-1 block text-xs font-medium text-slate-700">Cook Time (min)</span>
                            <input
                              type="number"
                              min="0"
                              step="1"
                              value={editCookTime}
                              onChange={(event) => {
                                setEditCookTime(event.target.value);
                                setEditValidationErrors((previous) => ({ ...previous, cookTime: "" }));
                              }}
                              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 focus:border-slate-400"
                            />
                            {editValidationErrors.cookTime ? (
                              <p className="mt-1 text-xs text-rose-600">{editValidationErrors.cookTime}</p>
                            ) : null}
                          </label>
                        </div>
                        <label className="block">
                          <span className="mb-1 block text-xs font-medium text-slate-700">Ingredients</span>
                          <input
                            type="text"
                            value={editIngredientsText}
                            onChange={(event) => {
                              setEditIngredientsText(event.target.value);
                              setEditValidationErrors((previous) => ({ ...previous, ingredients: "" }));
                            }}
                            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 focus:border-slate-400"
                          />
                          {editValidationErrors.ingredients ? (
                            <p className="mt-1 text-xs text-rose-600">{editValidationErrors.ingredients}</p>
                          ) : null}
                        </label>
                        <label className="block">
                          <span className="mb-1 block text-xs font-medium text-slate-700">Tags</span>
                          <input
                            type="text"
                            value={editTagsText}
                            onChange={(event) => {
                              setEditTagsText(event.target.value);
                              setEditValidationErrors((previous) => ({ ...previous, tags: "" }));
                            }}
                            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 focus:border-slate-400"
                          />
                          {editValidationErrors.tags ? (
                            <p className="mt-1 text-xs text-rose-600">{editValidationErrors.tags}</p>
                          ) : null}
                        </label>
                        <div className="flex gap-2">
                          <button
                            type="submit"
                            disabled={editSaving}
                            className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {editSaving ? "Saving..." : "Save Changes"}
                          </button>
                          <button
                            type="button"
                            onClick={cancelEditRecipe}
                            disabled={editSaving}
                            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            Cancel
                          </button>
                        </div>
                      </form>
                    ) : null}

                    <div className="mt-4 border-t border-slate-200 pt-4">
                      <h4 className="text-sm font-semibold text-slate-900">Comments</h4>

                      {(selectedRecipe.comments || []).length > 0 ? (
                        <ul className="mt-2 space-y-2">
                          {selectedRecipe.comments.map((comment) => (
                            <li key={comment.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <p>{comment.content}</p>
                                  {comment.created_at ? (
                                    <p className="mt-1 text-xs text-slate-500">
                                      {new Date(comment.created_at).toLocaleString()} · by {comment.created_by_username || "Unknown user"}
                                    </p>
                                  ) : null}
                                </div>
                                {currentUser && comment.created_by_username === currentUser.username ? (
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteComment(comment.id)}
                                    disabled={commentDeletingId === comment.id}
                                    className="rounded-md border border-rose-200 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    {commentDeletingId === comment.id ? "Removing..." : "Remove"}
                                  </button>
                                ) : null}
                              </div>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-2 text-sm text-slate-500">No comments yet.</p>
                      )}

                      <form onSubmit={handleAddComment} className="mt-3 flex flex-col gap-2 sm:flex-row">
                        <input
                          type="text"
                          value={commentText}
                          onChange={(event) => setCommentText(event.target.value)}
                          placeholder="Add a comment"
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none ring-0 placeholder:text-slate-400 focus:border-slate-400"
                        />
                        <button
                          type="submit"
                          disabled={commentSaving || !commentText.trim()}
                          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {commentSaving ? "Posting..." : "Post"}
                        </button>
                      </form>
                    </div>
                  </div>
                ) : null}

                <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">Tap a recipe for details</p>
                <ul className="space-y-3">
                {sortedRecipes.map((recipe) => (
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
                      <p className="mt-1 text-xs text-slate-500">By {recipe.created_by_username || "Unknown user"}</p>
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

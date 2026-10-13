return {
  {
    "xiyaowong/transparent.nvim",
    lazy = false, -- load on startup
    priority = 1000,
    config = function()
      require("transparent").setup({
        -- Optional: add groups you don't want to be transparent
        extra_groups = {},
        exclude_groups = {},
      })

      -- Enable transparency automatically
      vim.cmd("TransparentEnable")
    end,
  },
}

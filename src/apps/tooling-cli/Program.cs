// Copyright (c) 2026 Hellen
// Licensed under the PolyForm Noncommercial License 1.0.0

using System.CommandLine;
using Microsoft.Extensions.Logging;

var root = new RootCommand("tooling-cli");

root.SetHandler(() =>
{
    Console.WriteLine("tooling-cli is running.");
});

return await root.InvokeAsync(args);

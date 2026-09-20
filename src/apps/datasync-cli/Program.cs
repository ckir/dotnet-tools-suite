// Copyright (c) 2026 Costas Kirgoussios
// Licensed under the PolyForm Noncommercial License 1.0.0

using System;
using System.CommandLine;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

var services = new ServiceCollection()
    .AddLogging(builder => builder.AddConsole())
    .BuildServiceProvider();

var logger = services.GetRequiredService<ILoggerFactory>().CreateLogger("datasync-cli");

var root = new RootCommand("datasync-cli root command");

root.SetAction(_ =>
{
    logger.LogInformation("datasync-cli is running.");
    Console.WriteLine("datasync-cli executed.");
});

return await root.Parse(args).InvokeAsync();

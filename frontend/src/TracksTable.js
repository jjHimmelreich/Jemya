import React from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from "@tanstack/react-table";

const columnHelper = createColumnHelper();

function TracksTable({ data }) {
  const columns = [
    columnHelper.accessor("duration", {
      header: "Duration",
      cell: info => info.getValue(),
    }),
    columnHelper.accessor(row => row, {
      id: "track_name",
      header: "Track",
      cell: info => {
        const row = info.getValue();
        return row.spotify_link ? (
          <a
            href={row.spotify_link}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "#1db954", textDecoration: "none" }}
          >
            {row.track_name}
          </a>
        ) : (
          row.track_name
        );
      },
    }),
    columnHelper.accessor("artist", {
      header: "Artist",
      cell: info => info.getValue(),
    }),
    columnHelper.accessor("comment", {
      header: "Comment",
      cell: info => info.getValue(),
    }),
  ];

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div style={{ overflowX: "auto", marginTop: "20px" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th
                  key={header.id}
                  style={{
                    textAlign: "left",
                    padding: "8px",
                    borderBottom: "1px solid #4D4D4D",
                  }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr key={row.id}>
              {row.getVisibleCells().map(cell => (
                <td
                  key={cell.id}
                  style={{
                    padding: "8px",
                    borderBottom: "1px solid #2a2a2a",
                    color: "#e0e0e0",
                  }}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default TracksTable;
